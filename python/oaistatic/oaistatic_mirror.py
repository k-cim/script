#!/usr/bin/python3
# === File: oaistatic_mirror.py
# Version: 1.3.4
# Date: 2025-07-28 18:42:00 UTC
# Description: Transforme les liens HTML dépendants des fichiers Firefox/CDN en chemins locaux. Supporte md5, logs, assets multiples.

import os
import sys
import hashlib
import shutil
import argparse
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

# === Répertoires par défaut
OAISTATIC_BASE = Path.home() / "Dev/documentation/oaistatic"
HTML_DIR = OAISTATIC_BASE / "html"
LOG_DIR = OAISTATIC_BASE / "_log"
CDN_DIR = OAISTATIC_BASE / "cdn/assets"
PERSISTENT_DIR = OAISTATIC_BASE / "persistent"
EXTERNAL_DIR = OAISTATIC_BASE / "external_assets"

def slugify_filename(name):
    nfkd = unicodedata.normalize('NFKD', name)
    ascii_name = nfkd.encode('ASCII', 'ignore').decode('ascii')
    ascii_name = ascii_name.lower()
    ascii_name = ascii_name.replace('ç', 'c').replace('æ', 'ae').replace('œ', 'oe')
    return re.sub(r'[^a-zA-Z0-9._-]', '_', ascii_name)

def compute_md5(path):
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def copy_with_md5(source_path, dest_path):
    if dest_path.exists() and compute_md5(source_path) == compute_md5(dest_path):
        return False  # Aucun changement
    shutil.copy2(source_path, dest_path)
    return True

def mirror_assets(soup, base_dir, input_path, firefox_dir):
    tags = soup.find_all(['link', 'script', 'img', 'source'])
    log_entries = []
    timestamp = datetime.utcnow().isoformat()
    for idx, tag in enumerate(tags):
        attr = 'href' if tag.name in ['link'] else 'src'
        url = tag.get(attr)
        if not url:
            continue

        # CDN
        if 'cdn.oaistatic.com/assets/' in url:
            filename = url.split('/')[-1]
            local_path = CDN_DIR / filename
            tag[attr] = os.path.relpath(local_path, HTML_DIR)
            log_entries.append((timestamp, input_path.name, url, tag[attr], 'cdn'))
            continue

        # Persistent
        if 'persistent.oaistatic.com/' in url:
            subpath = url.split('persistent.oaistatic.com/')[-1]
            local_path = PERSISTENT_DIR / subpath
            tag[attr] = os.path.relpath(local_path, HTML_DIR)
            log_entries.append((timestamp, input_path.name, url, tag[attr], 'persistent'))
            continue

        # Firefox assets (_fichiers)
        if firefox_dir:
            url_path = Path(url)
            try:
                candidate = next(f for f in firefox_dir.rglob(url_path.name) if f.name == url_path.name)
            except StopIteration:
                continue

            clean_name = slugify_filename(candidate.name)
            dest_path = EXTERNAL_DIR / clean_name
            if copy_with_md5(candidate, dest_path):
                log_entries.append((timestamp, input_path.name, str(candidate), str(dest_path), candidate.suffix[1:]))

            tag[attr] = os.path.relpath(dest_path, HTML_DIR)

    # Patcher les import ES6 : import * as X from "https://cdn.oaistatic.com/assets/xxx.js"
    for script in soup.find_all('script'):
        if script.string:
            pattern = r'import\s+\*\s+as\s+(\w+)\s+from\s+[\'"](https://cdn\.oaistatic\.com/assets/[^\'"]+)[\'"];'
            matches = re.findall(pattern, script.string)
            for varname, fullurl in matches:
                filename = fullurl.split('/')[-1]
                local_path = CDN_DIR / filename
                replacement = f'import * as {varname} from "{os.path.relpath(local_path, HTML_DIR)}";'
                script.string = re.sub(
                    re.escape(f'import * as {varname} from "{fullurl}";'),
                    replacement,
                    script.string
                )
                log_entries.append((timestamp, input_path.name, fullurl, str(local_path), 'es6'))

    return log_entries

def write_log(log_entries, name):
    log_name = datetime.utcnow().strftime("%Y%m%dT%H%M%S") + f".{name}.log"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / log_name, 'w') as f:
        for entry in log_entries:
            f.write(" ; ".join(entry) + "\n")

def main():
    parser = argparse.ArgumentParser(description="Convertit les ressources HTML en chemins locaux.")
    parser.add_argument("input", help="Fichier HTML source")
    parser.add_argument("--assets-dir", help="Nom du répertoire _fichiers si différent")
    parser.add_argument("--silent", action="store_true", help="Mode silence total")
    parser.add_argument("--verbose", action="store_true", help="Affiche les opérations")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Fichier HTML introuvable : {input_path}")
        sys.exit(1)

    # Firefox folder associé
    base_name = input_path.stem
    if args.assets_dir:
        firefox_dir = Path(args.assets_dir)
    else:
        firefox_dir = input_path.parent / f"{base_name}_fichiers"

    if not firefox_dir.exists():
        if not args.silent:
            resp = input(f"📁 Dossier Firefox non trouvé : {firefox_dir}. Continuer ? (y/n) ")
            if resp.strip().lower() != 'y':
                sys.exit(1)
        firefox_dir = None

    with open(input_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    HTML_DIR.mkdir(parents=True, exist_ok=True)
    output_path = HTML_DIR / f"{base_name}-mod.html"

    log_entries = mirror_assets(soup, OAISTATIC_BASE, input_path, firefox_dir)
    write_log(log_entries, input_path.name)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(str(soup))

    if not args.silent:
        print(f"✅ HTML modifié : {output_path}")
        print(f"🪵 Log : {LOG_DIR / (datetime.utcnow().strftime('%Y%m%dT%H%M%S') + f'.{input_path.name}.log')}")

if __name__ == "__main__":
    main()
