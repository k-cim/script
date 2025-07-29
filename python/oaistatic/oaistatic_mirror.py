#!/usr/bin/env python3
# === File: oaistatic_mirror.py
# Version: 1.3.14
# Date: 2025-07-29 20:38:00 UTC
# Description: Convertit les ressources HTML locales/distant en liens offline, avec redirection POSIX compatible (stdin/stdout), logging complet, slugification avancée et fallback distant.

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

# Répertoires de base (config par défaut)
OAISTATIC_BASE = Path.home() / "Dev/documentation/oaistatic"
HTML_DIR = OAISTATIC_BASE / "html"
LOG_DIR = OAISTATIC_BASE / "_log"
CDN_DIR = OAISTATIC_BASE / "cdn/assets"
PERSISTENT_DIR = OAISTATIC_BASE / "persistent"
EXTERNAL_DIR = OAISTATIC_BASE / "external_assets"

for p in [HTML_DIR, LOG_DIR, CDN_DIR, PERSISTENT_DIR, EXTERNAL_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# Slugification avancée (accents, symboles, etc.)
def slugify_filename(name):
    trans = str.maketrans({
        'É': 'e', 'È': 'e', 'Ê': 'e', 'Ë': 'e',
        'À': 'a', 'Â': 'a', 'Ä': 'a',
        'Ô': 'o', 'Ö': 'o',
        'Û': 'u', 'Ü': 'u',
        'Î': 'i', 'Ï': 'i',
        'Ç': 'c', 'œ': 'oe', 'Œ': 'oe',
        '€': 'e', '$': 's', '&': '', '@': 'at'
    })
    name = name.translate(trans)
    name = re.sub(r"[^\w\s-]", "-", name, flags=re.UNICODE)
    name = re.sub(r"[-\s]+", "-", name).strip("-_")
    return name.lower()

# MD5 local
def file_md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for c in iter(lambda: f.read(8192), b''):
            h.update(c)
    return h.hexdigest()

# Log écriture
def write_log_entry(logfile, entry):
    with open(logfile, 'a') as f:
        f.write(f"{datetime.utcnow().isoformat()} ; {entry}\n")

# Téléchargement distant
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

# Traitement HTML
def process_html(input_html, args):
    stdin_mode = input_html == "-"
    stdin_fallback = not sys.stdin.isatty()
    raw_data = ""

    # Lecture entrée
    if stdin_mode or (input_html is None and stdin_fallback):
        raw_data = sys.stdin.read()
        logical_name = args.stdin_name or "stdin"
        input_path = Path(logical_name)
        slug_name = slugify_filename(logical_name)
    else:
        input_path = Path(input_html)
        if not input_path.exists():
            print(f"❌ Fichier introuvable : {input_html}")
            return
        with open(input_path, "r", encoding="utf-8") as f:
            raw_data = f.read()
        slug_name = slugify_filename(input_path.name)

    mod_name = f"{slug_name}-mod.html"
    mod_path = HTML_DIR / mod_name
    log_path = LOG_DIR / f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.{mod_name}.log"

    # Tête log
    write_log_entry(log_path, f"# === oaistatic_mirror.py – Version: 1.3.14 – Date: {datetime.utcnow().isoformat()} ===")
    write_log_entry(log_path, f"Fichier analysé : {input_path.name} @ {datetime.now()}")
    if input_path.name != slug_name:
        write_log_entry(log_path, f"Slugification : {input_path.name} → {slug_name}")

    # Cherche dossier d’assets
    rep_used = None
    default_dir = input_path.stem + "_fichiers"
    local_dir = input_path.parent / default_dir
    if local_dir.exists():
        rep_used = default_dir
    elif args.force_dir:
        if Path(args.force_dir).exists():
            rep_used = args.force_dir
    elif not args.no_prompt:
        print("⚠️ Aucun répertoire local d’assets trouvé.")
        print("Tentative de téléchargement des éléments uniquement")
        print("Vous pouvez utiliser l’option --force-dir DIRECTORY")
        resp = input("➤ Voulez-vous continuer ? [y/n] ")
        if resp.lower() != "y":
            print("⏹️ Annulé.")
            return

    write_log_entry(log_path, f"Répertoire utilisé : {rep_used or 'Aucun (force-dir ou distant uniquement)'}")

    pattern = r'(src|href)=["\']([^"\']+)["\']'
    matches = re.findall(pattern, raw_data)

    for _, url in matches:
        parsed = urlparse(url)
        if parsed.scheme.startswith("http"):
            filename = os.path.basename(parsed.path)
        else:
            filename = os.path.basename(url)

        suffix = Path(filename).suffix[1:]
        origine = "local"
        if "cdn.oaistatic.com" in url:
            target_path = CDN_DIR / filename
            new_link = f"../cdn/assets/{filename}"
            origine = "cdn"
        elif "persistent.oaistatic.com" in url:
            target_path = PERSISTENT_DIR / filename
            new_link = f"../persistent/{filename}"
            origine = "persistent"
        else:
            target_path = EXTERNAL_DIR / filename
            new_link = f"../external_assets/{filename}"

        if not target_path.exists():
            status = "non trouvé"
            if rep_used:
                src = Path(rep_used) / filename
                if src.exists():
                    shutil.copy2(src, target_path)
                    status = "copié – local"
                else:
                    if download_file(url, target_path):
                        status = "réécrit – distant (non trouvé localement)"
            else:
                if download_file(url, target_path):
                    status = "réécrit – distant"
        else:
            status = "identique – déjà présent"

        raw_data = raw_data.replace(url, new_link)
        write_log_entry(log_path, f"{input_path.name} ; {url} ; {new_link} ; {suffix} ; {status} ; origine: {origine}")

    if args.stdout:
        print(raw_data)
    else:
        with open(mod_path, "w", encoding="utf-8") as f:
            f.write(raw_data)
        print(f"✅ Fichier modifié : {mod_path}")
        print(f"🪵 Log : {log_path}")

# CLI
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_html", nargs="?", help="Fichier HTML source ou - pour stdin")
    parser.add_argument("--stdin-name", help="Nom logique du fichier si lecture depuis stdin")
    parser.add_argument("--stdout", action="store_true", help="Écrit le HTML modifié dans stdout")
    parser.add_argument("--silent", action="store_true", help="N’affiche aucun message")
    parser.add_argument("--verbose", action="store_true", help="Affiche les opérations")
    parser.add_argument("--force", action="store_true", help="Force l’écrasement du fichier HTML modifié")
    parser.add_argument("--no-prompt", action="store_true", help="Ne jamais poser de question")
    parser.add_argument("--force-dir", help="Répertoire à utiliser si _fichiers absent")
    parser.add_argument("--no-log", action="store_true", help="Désactive les journaux")

    args = parser.parse_args()
    if args.verbose:
        print("🔧 Démarrage avec options :", args)

    if not args.input_html and not sys.stdin.isatty():
        args.input_html = "-"

    process_html(args.input_html, args)

if __name__ == "__main__":
    main()
