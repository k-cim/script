#!/usr/bin/python3
# === File: oaistatic_mirror.py
# Version: 1.3.15
# Date: 2025-07-29 23:34:00 UTC
# Description: Télécharge, convertit et relie les ressources HTML/CDN/externes pour lecture offline, avec support POSIX stdin/stdout, logs détaillés, et compatibilité navigateur étendue.

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

# Répertoires de base (modifiable à terme via JSON externe)
OAISTATIC_BASE = Path.home() / "Dev/documentation/oaistatic"
HTML_DIR = OAISTATIC_BASE / "html"
LOG_DIR = OAISTATIC_BASE / "_log"
CDN_DIR = OAISTATIC_BASE / "cdn/assets"
PERSISTENT_DIR = OAISTATIC_BASE / "persistent"
EXTERNAL_DIR = OAISTATIC_BASE / "external_assets"

for p in [HTML_DIR, LOG_DIR, CDN_DIR, PERSISTENT_DIR, EXTERNAL_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# Slugification personnalisée (accents, symboles)
def slugify_filename(name):
    substitutions = {
        "œ": "oe", "Œ": "oe", "€": "e", "$": "s", "ç": "c", "Ç": "c",
        "é": "e", "è": "e", "ê": "e", "ë": "e", "É": "e", "È": "e", "Ê": "e", "Ë": "e",
        "à": "a", "â": "a", "ä": "a", "À": "a", "Â": "a", "Ä": "a",
        "î": "i", "ï": "i", "Î": "i", "Ï": "i", "ô": "o", "ö": "o", "Ô": "o", "Ö": "o",
        "û": "u", "ù": "u", "ü": "u", "Û": "u", "Ù": "u", "Ü": "u",
        "&": "et"
    }
    for src, tgt in substitutions.items():
        name = name.replace(src, tgt)
    name = re.sub(r"[^\w\s.-]", "-", name)
    name = re.sub(r"[-\s]+", "-", name)
    return name.lower()

# Hash MD5
def file_md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

# Écriture dans le log
def write_log_entry(log_path, entry):
    with open(log_path, "a") as f:
        f.write(f"{datetime.utcnow().isoformat()} ; {entry}\n")

# Téléchargement simple
def download_file(url, dest):
    try:
        import requests
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            with open(dest, 'wb') as f:
                f.write(r.content)
            return True
    except:
        pass
    return False

# Traitement d'un fichier HTML
def process_html_file(html, input_name, args):
    slug_name = slugify_filename(input_name)
    mod_name = f"{slug_name}-mod.html"
    mod_path = HTML_DIR / mod_name
    log_name = f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.{mod_name}.log"
    log_path = LOG_DIR / log_name

    # === En-tête du log
    write_log_entry(log_path, f"# === oaistatic_mirror.py – Version: 1.3.15 – Date: {datetime.utcnow().isoformat()} ===")
    write_log_entry(log_path, f"Fichier analysé : {input_name} @ {datetime.utcnow().isoformat()}")
    if input_name != slug_name:
        write_log_entry(log_path, f"Slugification : {input_name} → {slug_name}")

    # Vérif mod_path existant
    if mod_path.exists() and not args.force and not args.no_prompt:
        resp = input(f"⚠️ Le fichier {mod_path.name} existe. Remplacer ? (y/n) ")
        if resp.lower() != "y":
            print("⏹️ Annulé.")
            return

    # Dossier _fichiers
    input_stem = Path(input_name).stem
    local_dir = Path(input_stem + "_fichiers")
    rep_used = None
    if local_dir.exists():
        rep_used = local_dir
    elif args.force_dir and Path(args.force_dir).exists():
        rep_used = Path(args.force_dir)
    else:
        print("⚠️ Aucun répertoire local d’assets trouvé.")
        print("Tentative de téléchargement des éléments uniquement")
        print("Vous pouvez utiliser l’option --force-dir DIRECTORY")
        resp = input("➤ Voulez-vous continuer ? [y/n] ")
        if resp.lower() != "y":
            return
    write_log_entry(log_path, f"Répertoire utilisé : {rep_used if rep_used else 'Aucun (force-dir ou distant uniquement)'}")

    # Extraction et traitement
    pattern = r'(src|href)=["\']([^"\']+)["\']'
    matches = re.findall(pattern, html)

    for _, url in matches:
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        suffix = Path(filename).suffix[1:]
        if not filename:
            continue

        if "cdn.oaistatic.com" in parsed.netloc:
            new_path = CDN_DIR / filename
            new_link = f"../cdn/assets/{filename}"
            origine = "cdn"
        elif "persistent.oaistatic.com" in parsed.netloc:
            new_path = PERSISTENT_DIR / filename
            new_link = f"../persistent/{filename}"
            origine = "persistent"
        elif parsed.scheme in ["http", "https"]:
            new_path = EXTERNAL_DIR / filename
            new_link = f"../external_assets/{filename}"
            origine = "local"
        else:
            new_path = EXTERNAL_DIR / filename
            new_link = f"../external_assets/{filename}"
            origine = "local"

        # Copie ou DL
        if not new_path.exists():
            if rep_used and (rep_used / filename).exists():
                shutil.copy2(rep_used / filename, new_path)
                status = "copié – local"
            elif download_file(url, new_path):
                status = "réécrit – distant"
            else:
                status = "non trouvé"
        else:
            status = "identique – déjà présent"

        if not args.silent:
            print(f"🔁 {filename} → {new_link}")
        html = html.replace(url, new_link)
        write_log_entry(log_path, f"{input_name} ; {url} ; {new_link} ; {suffix} ; {status} ; origine: {origine}")

    # Sortie
    if args.stdout:
        sys.stdout.write(html)
    else:
        with open(mod_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"✅ HTML modifié : {mod_path}")
        print(f"🪵 Log : {log_path}")

# Main CLI
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_html", nargs="?", help="Fichier HTML source ou '-' pour stdin")
    parser.add_argument("--stdin-name", help="Nom factice si l’entrée provient d’un tube")
    parser.add_argument("--silent", action="store_true", help="Mode silencieux")
    parser.add_argument("--verbose", action="store_true", help="Mode verbeux")
    parser.add_argument("--force", action="store_true", help="Force l'écrasement")
    parser.add_argument("--no-prompt", action="store_true", help="N’interrompt jamais")
    parser.add_argument("--force-dir", help="Répertoire à utiliser pour assets")
    parser.add_argument("--stdout", action="store_true", help="Sortie vers STDOUT")

    args = parser.parse_args()

    if args.input_html == "-" or not args.input_html:
        html = sys.stdin.read()
        name = args.stdin_name or "stdin.html"
        process_html_file(html, name, args)
    else:
        input_path = Path(args.input_html)
        if not input_path.exists():
            print(f"❌ Fichier introuvable : {args.input_html}")
            return
        with open(input_path, "r", encoding="utf-8") as f:
            html = f.read()
        process_html_file(html, input_path.name, args)

if __name__ == "__main__":
    main()
