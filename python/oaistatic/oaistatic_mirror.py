#!/usr/bin/python3
# === File: oaistatic_mirror.py
# Version: 1.3.10
# Date: 2025-07-29 06:26:00 UTC
# Description: Télécharge, convertit et relie les ressources HTML/CDN/Firefox pour lecture offline avec logs, checksum, redirection externe forcée, et modes verbeux/silencieux.

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

# Création répertoires si nécessaires
for path in [HTML_DIR, LOG_DIR, CDN_DIR, PERSISTENT_DIR, EXTERNAL_DIR]:
    path.mkdir(parents=True, exist_ok=True)

# Slugify partiel pour noms de fichiers
def slugify_filename(name):
    name = re.sub(r"[^\w\s-]", "-", name)
    name = re.sub(r"[-\s]+", "-", name)
    return name.lower()

# Hash MD5
def file_md5(filepath):
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

# Log écriture
def write_log_entry(logfile, entry):
    with open(logfile, 'a') as log:
        log.write(f"{datetime.utcnow().isoformat()} ; {entry}\n")

# Téléchargement distant
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

# Traitement principal
def process_html(input_html, args):
    input_path = Path(input_html)
    if not input_path.exists():
        print(f"❌ Fichier introuvable : {input_path}")
        return

    slug_name = slugify_filename(input_path.name)
    mod_name = f"{slug_name}-mod.html"
    mod_path = HTML_DIR / mod_name
    log_path = LOG_DIR / f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.{input_path.name}.log"

    # Timestamp et slug
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

    dirname = input_path.stem + "_fichiers"
    dirpath = input_path.parent / dirname
    rep_used = None

    if dirpath.exists():
        rep_used = dirname
    elif args.force_dir and Path(args.force_dir).exists():
        rep_used = args.force_dir
    else:
        print(f"📁 Dossier Firefox non trouvé : {dirname}. Continuer ? (y/n) ", end="")
        if not args.force and input().lower() != 'y':
            return
    write_log_entry(log_path, f"Répertoire utilisé : {rep_used or 'Aucun (force-dir ou distant uniquement)'}")

    # Extraction des liens
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
                downloaded = download_file(url, new_path)
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
                    downloaded = download_file(url, new_path)
                    status = "réécrit – distant (non trouvé localement)" if downloaded else "non trouvé"
        else:
            status = "identique – déjà présent"

        if not args.silent:
            print(f"🔁 {filename} → {new_link}")

        html = html.replace(url, new_link)
        write_log_entry(log_path, f"{input_path.name} ; {url} ; {new_link} ; {suffix} ; {status} ; origine: {origine}")

    # Sauvegarde du fichier modifié
    with open(mod_path, 'w', encoding="utf-8") as f:
        f.write(html)

    print(f"✅ HTML modifié : {mod_path}")
    print(f"🪵 Log : {log_path}")

# CLI
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
