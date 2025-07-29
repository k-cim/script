#!/usr/bin/python3
# === File: oaistatic_mirror.py
# Version: 1.3.12
# Date: 2025-07-29 23:45:00 UTC
# Description: Traitement HTML offline avec liens normalisés, téléchargement conditionnel, log enrichi, et slug custom sans dépendance externe.

import os
import re
import sys
import json
import shutil
import hashlib
import argparse
import unicodedata
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

# === Configuration ===
VERSION = "1.3.12"
OAISTATIC_BASE = Path.home() / "Dev/documentation/oaistatic"
HTML_DIR = OAISTATIC_BASE / "html"
LOG_DIR = OAISTATIC_BASE / "_log"
CDN_DIR = OAISTATIC_BASE / "cdn/assets"
PERSISTENT_DIR = OAISTATIC_BASE / "persistent"
EXTERNAL_DIR = OAISTATIC_BASE / "external_assets"
ASSET_SUFFIX = os.environ.get("OAISTATIC_ASSET_DIR_SUFFIX", "_fichiers")

for path in [HTML_DIR, LOG_DIR, CDN_DIR, PERSISTENT_DIR, EXTERNAL_DIR]:
    path.mkdir(parents=True, exist_ok=True)

def custom_slugify(text):
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    replacements = {
        'œ': 'oe', 'Œ': 'oe',
        '€': 'e', '$': 's',
        'ç': 'c', 'Ç': 'c',
        '&': 'et'
    }
    text = ''.join(replacements.get(c, c) for c in text)
    text = re.sub(r'[^a-zA-Z0-9._-]', '-', text)
    return re.sub(r'-+', '-', text).strip('-_.').lower()

def file_md5(filepath):
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def write_log_entry(logfile, entry):
    with open(logfile, 'a') as log:
        log.write(f"{datetime.utcnow().isoformat()} ; {entry}\n")

def download_file(url, dest, verbose=False):
    try:
        import requests
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            with open(dest, 'wb') as f:
                f.write(r.content)
            return True
        if verbose:
            print(f"⚠️ Échec téléchargement : {r.status_code} → {url}")
        return False
    except Exception as e:
        if verbose:
            print(f"⚠️ Exception réseau : {e} → {url}")
        return False

def process_html(input_html, args):
    input_path = Path(input_html)
    if not input_path.exists():
        print(f"❌ Fichier introuvable : {input_path}")
        return

    slug_name = custom_slugify(input_path.name)
    mod_name = f"{slug_name}-mod.html"
    mod_path = HTML_DIR / mod_name
    log_path = LOG_DIR / f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.{input_path.name}.log"

    with open(log_path, 'w') as log:
        log.write(f"# === oaistatic_mirror.py – Version: {VERSION} – Date: {datetime.utcnow().isoformat()} ===\n")

    stat = input_path.stat()
    write_log_entry(log_path, f"Fichier analysé : {input_path.name} @ {datetime.fromtimestamp(stat.st_mtime)}")
    if input_path.name != slug_name:
        write_log_entry(log_path, f"Slugification : {input_path.name} → {slug_name}")

    if mod_path.exists() and not args.force and not args.no_prompt:
        resp = input(f"⚠️ Le fichier {mod_path.name} existe. Remplacer ? (y/n) ")
        if resp.lower() != 'y':
            print("⏹️ Annulé.")
            return

    try:
        with open(input_path, 'r', encoding="utf-8") as f:
            html = f.read()
    except Exception as e:
        print(f"❌ Erreur lecture : {e}")
        return

    base_name = input_path.stem
    dir_guess = Path(input_path.parent / (base_name + ASSET_SUFFIX))
    rep_used = None

    if dir_guess.exists():
        rep_used = dir_guess.name
    elif args.force_dir and Path(args.force_dir).exists():
        rep_used = args.force_dir

    write_log_entry(log_path, f"Répertoire utilisé : {rep_used or 'Aucun (force-dir ou distant uniquement)'}")

    # === Traitement des liens HTTP
    pattern = r'(src|href)=["\'](https?://[^"\']+)["\']'
    matches = re.findall(pattern, html)

    for _, url in matches:
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        suffix = Path(filename).suffix[1:]
        if "cdn.oaistatic.com" in parsed.netloc:
            new_path = CDN_DIR / filename
            new_link = f"../cdn/assets/{filename}"
            origine = "cdn"
        elif "persistent.oaistatic.com" in parsed.netloc:
            new_path = PERSISTENT_DIR / filename
            new_link = f"../persistent/{filename}"
            origine = "persistent"
        else:
            new_path = EXTERNAL_DIR / filename
            new_link = f"../external_assets/{filename}"
            origine = "local"

        if not new_path.exists():
            if not rep_used:
                downloaded = download_file(url, new_path, verbose=args.verbose)
                status = "réécrit – distant" if downloaded else "non téléchargé"
            else:
                src_file = Path(rep_used) / filename
                if src_file.exists():
                    if not new_path.exists() or file_md5(src_file) != file_md5(new_path):
                        shutil.copy2(src_file, new_path)
                        status = "copié – local"
                    else:
                        status = "identique – déjà présent"
                else:
                    downloaded = download_file(url, new_path, verbose=args.verbose)
                    status = "réécrit – distant (non trouvé localement)" if downloaded else "non trouvé"
        else:
            status = "identique – déjà présent"

        if args.verbose:
            print(f"🔁 {filename} → {new_link}")

        html = html.replace(url, new_link)
        write_log_entry(log_path, f"{input_path.name} ; {url} ; {new_link} ; {suffix} ; {status} ; origine: {origine}")

    # === Traitement des chemins locaux type xxx/filename
    local_ref = re.findall(r'(href|src)=["\']([^"\':]+/[^"\']+)["\']', html)
    for _, local in local_ref:
        if local.startswith("http"): continue
        parts = local.split("/")
        if len(parts) != 2: continue
        folder, filename = parts
        dest_path = EXTERNAL_DIR / filename
        suffix = Path(filename).suffix[1:]
        src_file = Path(input_path.parent) / folder / filename
        new_link = f"../external_assets/{filename}"

        if src_file.exists():
            if not dest_path.exists() or file_md5(src_file) != file_md5(dest_path):
                shutil.copy2(src_file, dest_path)
                status = "copié – local"
            else:
                status = "identique – déjà présent"
        else:
            status = "introuvable – réécrit quand même"

        html = html.replace(local, new_link)
        write_log_entry(log_path, f"{input_path.name} ; {local} ; {new_link} ; {suffix} ; {status} ; origine: local")
        if args.verbose:
            print(f"🔃 {local} → {new_link}")

    with open(mod_path, 'w', encoding="utf-8") as f:
        f.write(html)

    if not args.silent:
        print(f"✅ HTML modifié : {mod_path}")
        print(f"🪵 Log : {log_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_html", help="Fichier HTML source")
    parser.add_argument("--silent", action="store_true", help="Mode silencieux")
    parser.add_argument("--verbose", action="store_true", help="Affiche les opérations")
    parser.add_argument("--force", action="store_true", help="Force l’écrasement du HTML modifié")
    parser.add_argument("--no-prompt", action="store_true", help="N’interrompt jamais avec une question")
    parser.add_argument("--force-dir", help="Répertoire à utiliser s’il n’est pas trouvé")
    parser.add_argument("--no-log", action="store_true", help="Désactive l’écriture du journal")

    args = parser.parse_args()
    if args.verbose:
        print("🔧 Démarrage avec options :", args)

    process_html(args.input_html, args)

if __name__ == "__main__":
    main()
