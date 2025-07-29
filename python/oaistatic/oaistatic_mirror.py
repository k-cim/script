#!/usr/bin/python3
# === File: oaistatic_mirror.py
# Version: 1.3.13
# Date: 2025-07-29 18:02:29 UTC
# Description: Traitement HTML offline (CDN/external) avec log structuré, stdin/stdout auto et vérifications strictes

import os
import re
import sys
import json
import shutil
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

# Répertoires de base
OAISTATIC_BASE = Path.home() / "Dev/documentation/oaistatic"
HTML_DIR = OAISTATIC_BASE / "html"
LOG_DIR = OAISTATIC_BASE / "_log"
CDN_DIR = OAISTATIC_BASE / "cdn/assets"
PERSISTENT_DIR = OAISTATIC_BASE / "persistent"
EXTERNAL_DIR = OAISTATIC_BASE / "external_assets"

for path in [HTML_DIR, LOG_DIR, CDN_DIR, PERSISTENT_DIR, EXTERNAL_DIR]:
    path.mkdir(parents=True, exist_ok=True)

# Slugify amélioré
def slugify_filename(name):
    map_custom = str.maketrans({
        'É': 'e', 'é': 'e', 'È': 'e', 'è': 'e',
        'Ç': 'c', 'ç': 'c', '€': 'e', 'Œ': 'oe', 'œ': 'oe',
        '&': '-', '$': 's', 'À': 'a', 'à': 'a',
        'Ï': 'i', 'ï': 'i', 'Î': 'i', 'î': 'i',
    })
    name = name.translate(map_custom)
    name = re.sub(r"[^\w\s-]", "-", name)
    name = re.sub(r"[-\s]+", "-", name)
    return name.lower()

def file_md5(filepath):
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def write_log_entry(logfile, entry):
    with open(logfile, 'a') as log:
        log.write(f"{datetime.utcnow().isoformat()} ; {entry}\n")

def download_file(url, dest):
    try:
        import requests
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            with open(dest, 'wb') as f:
                f.write(r.content)
            return True
        return False
    except:
        return False

def process_html_stream(html, input_name="stdin", args=None):
    slug_name = slugify_filename(input_name)
    mod_name = f"{slug_name}-mod.html"
    log_path = LOG_DIR / f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.{mod_name}.log"
    write_log_entry(log_path, f"# === oaistatic_mirror.py – Version: 1.3.13 – Date: {datetime.utcnow().isoformat()} ===")
    write_log_entry(log_path, f"Fichier analysé : {input_name}")
    if input_name != slug_name:
        write_log_entry(log_path, f"Slugification : {input_name} → {slug_name}")

    # Pas de dossier local si STDIN
    write_log_entry(log_path, "Répertoire utilisé : Aucun (STDIN ou distant uniquement)")

    pattern = r'(src|href)=["\'](https?://[^"\']+|[^"\']+_fichiers/[^"\']+)["\']'
    matches = re.findall(pattern, html)

    for _, url in matches:
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        suffix = Path(filename).suffix[1:]
        origine = "local"
        if url.startswith("https://cdn.oaistatic.com"):
            new_path = CDN_DIR / filename
            new_link = f"../cdn/assets/{filename}"
            origine = "cdn"
        elif url.startswith("https://persistent.oaistatic.com"):
            new_path = PERSISTENT_DIR / filename
            new_link = f"../persistent/{filename}"
            origine = "persistent"
        else:
            new_path = EXTERNAL_DIR / filename
            new_link = f"../external_assets/{filename}"

        if not new_path.exists():
            downloaded = download_file(url, new_path)
            status = "réécrit – distant" if downloaded else "non téléchargé"
        else:
            status = "identique – déjà présent"

        html = html.replace(url, new_link)
        write_log_entry(log_path, f"{input_name} ; {url} ; {new_link} ; {suffix} ; {status} ; origine: {origine}")

    if sys.stdout.isatty():
        out_path = HTML_DIR / mod_name
        with open(out_path, 'w', encoding="utf-8") as f:
            f.write(html)
        print(f"✅ HTML modifié : {out_path}")
        print(f"🪵 Log : {log_path}")
    else:
        sys.stdout.write(html)

def process_html_file(input_html, args):
    input_path = Path(input_html)
    if not input_path.exists():
        print(f"❌ Fichier introuvable : {input_path}")
        return

    slug_name = slugify_filename(input_path.name)
    mod_name = f"{slug_name}-mod.html"
    mod_path = HTML_DIR / mod_name
    log_path = LOG_DIR / f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.{mod_name}.log"

    stat = input_path.stat()
    write_log_entry(log_path, f"# === oaistatic_mirror.py – Version: 1.3.13 – Date: {datetime.utcnow().isoformat()} ===")
    write_log_entry(log_path, f"Fichier analysé : {input_path.name} @ {datetime.fromtimestamp(stat.st_mtime)}")
    if input_path.name != slug_name:
        write_log_entry(log_path, f"Slugification : {input_path.name} → {slug_name}")

    if mod_path.exists() and not args.force and not args.no_prompt:
        resp = input(f"⚠️ Le fichier {mod_path.name} existe. Remplacer ? (y/n) ")
        if resp.lower() != 'y':
            print("⏹️ Annulé.")
            return

    html = input_path.read_text(encoding="utf-8")
    dirname = input_path.stem + "_fichiers"
    dirpath = input_path.parent / dirname
    rep_used = None

    if dirpath.exists():
        rep_used = dirname
    elif args.force_dir and Path(args.force_dir).exists():
        rep_used = args.force_dir
    else:
        print("⚠️ Aucun répertoire local d’assets trouvé.\n"
              "Tentative de téléchargement des éléments uniquement.\n"
              "Vous pouvez utiliser l’option --force-dir <chemin> pour forcer un répertoire.\n"
              "\n➤ Voulez-vous continuer ? [y/N]", end=" ")
        if not args.force and input().strip().lower() != 'y':
            return

    write_log_entry(log_path, f"Répertoire utilisé : {rep_used or 'Aucun (force-dir ou distant uniquement)'}")

    pattern = r'(src|href)=["\'](https?://[^"\']+|[^"\']+_fichiers/[^"\']+)["\']'
    matches = re.findall(pattern, html)

    for _, url in matches:
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        suffix = Path(filename).suffix[1:]
        origine = "local"
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

        if not new_path.exists():
            if rep_used:
                src_file = Path(rep_used) / filename
                if src_file.exists():
                    shutil.copy2(src_file, new_path)
                    status = "copié – local"
                else:
                    downloaded = download_file(url, new_path)
                    status = "réécrit – distant" if downloaded else "non trouvé"
            else:
                downloaded = download_file(url, new_path)
                status = "réécrit – distant" if downloaded else "non téléchargé"
        else:
            status = "identique – déjà présent"

        html = html.replace(url, new_link)
        write_log_entry(log_path, f"{input_path.name} ; {url} ; {new_link} ; {suffix} ; {status} ; origine: {origine}")

    with open(mod_path, 'w', encoding="utf-8") as f:
        f.write(html)

    print(f"✅ HTML modifié : {mod_path}")
    print(f"🪵 Log : {log_path}")

# Entrée CLI
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_html", nargs="?", help="Fichier HTML source")
    parser.add_argument("--silent", action="store_true", help="Mode silencieux")
    parser.add_argument("--force", action="store_true", help="Écrase le fichier modifié")
    parser.add_argument("--no-prompt", action="store_true", help="N’interrompt jamais avec une question")
    parser.add_argument("--force-dir", help="Chemin d’un dossier à forcer")
    parser.add_argument("--no-log", action="store_true", help="N’enregistre aucun journal")

    args = parser.parse_args()

    if not sys.stdin.isatty() and not args.input_html:
        html = sys.stdin.read()
        process_html_stream(html, "stdin", args)
    elif args.input_html:
        process_html_file(args.input_html, args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
