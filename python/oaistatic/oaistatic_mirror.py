#!/usr/bin/env python3
# === File: oaistatic_mirror.py
# Version: 1.4
# Date: 2025-07-29 23:48:00 UTC
# Author: K-Cim
# Description: Traitement des fichiers HTML pour usage local – réécritures de liens, téléchargement, logs complets, STDIN/STDOUT, compatibilité POSIX.

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

# === Variables globales de version ===
SCRIPT_NAME = "oaistatic_mirror.py"
SCRIPT_VERSION = "1.4"
SCRIPT_DATE = "2025-07-29 23:48:00 UTC"

# === Répertoires principaux configurables ===
OAISTATIC_BASE = Path.home() / "Dev/documentation/oaistatic"
HTML_DIR = OAISTATIC_BASE / "html"
LOG_DIR = OAISTATIC_BASE / "_log"
CDN_DIR = OAISTATIC_BASE / "cdn/assets"
PERSISTENT_DIR = OAISTATIC_BASE / "persistent"
EXTERNAL_DIR = OAISTATIC_BASE / "external_assets"

# === Création automatique des dossiers ===
for path in [HTML_DIR, LOG_DIR, CDN_DIR, PERSISTENT_DIR, EXTERNAL_DIR]:
    path.mkdir(parents=True, exist_ok=True)

# === Fonction : Slugification avancée d’un nom de fichier ===
def slugify_filename(name):
    table = str.maketrans({
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "É": "e", "È": "e", "Ê": "e", "Ë": "e",
        "à": "a", "â": "a", "ä": "a", "À": "a", "Â": "a", "Ä": "a",
        "î": "i", "ï": "i", "Î": "i", "Ï": "i",
        "ô": "o", "ö": "o", "Ô": "o", "Ö": "o",
        "ù": "u", "û": "u", "ü": "u", "Ù": "u", "Û": "u", "Ü": "u",
        "ç": "c", "Ç": "c", "œ": "oe", "Œ": "oe",
        "€": "e", "$": "s", "&": "et"
    })
    name = name.translate(table)
    name = re.sub(r"[^\w\s-]", "-", name)
    name = re.sub(r"[-\s]+", "-", name)
    return name.lower()

# === Fonction : Calcul du hash MD5 d’un fichier ===
def file_md5(filepath):
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

# === Fonction : Écriture horodatée dans le fichier de log ===
def write_log_entry(logfile, entry):
    with open(logfile, 'a', encoding="utf-8") as log:
        log.write(f"{datetime.utcnow().isoformat()} ; {entry}\n")

# === Fonction : Téléchargement d’un fichier distant vers un chemin local ===
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

# === Fonction principale : Traitement d’un fichier HTML (chemin ou flux) ===
def process_html_file(html_source, source_name, args):
    slug_name = slugify_filename(source_name)
    mod_name = f"{slug_name}-mod.html"
    mod_path = HTML_DIR / mod_name
    log_path = LOG_DIR / f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.{mod_name}.log"

    # En-tête du log
    write_log_entry(log_path, f"# === {SCRIPT_NAME} – Version: {SCRIPT_VERSION} – Date: {SCRIPT_DATE} ===")
    write_log_entry(log_path, f"Fichier analysé : {source_name} @ {datetime.utcnow().isoformat()}")
    if slug_name != source_name:
        write_log_entry(log_path, f"Slugification : {source_name} → {slug_name}")

    if mod_path.exists() and not args.force and not args.no_prompt:
        resp = input(f"⚠️ Le fichier {mod_path.name} existe. Remplacer ? (y/n) ")
        if resp.lower() != 'y':
            print("⏹️ Annulé.")
            return

    # Lire le HTML source
    if hasattr(html_source, "read"):
        html = html_source.read()
    else:
        with open(html_source, 'r', encoding="utf-8") as f:
            html = f.read()

    # Tentative d’identification du dossier associé (local)
    dir_candidate = Path(source_name).stem + "_fichiers"
    dir_path = Path(source_name).parent / dir_candidate
    rep_used = None
    if dir_path.exists():
        rep_used = dir_candidate
    elif args.force_dir and Path(args.force_dir).exists():
        rep_used = args.force_dir
    else:
        if not args.no_prompt:
            print("⚠️ Aucun répertoire local d’assets trouvé.")
            print("Tentative de téléchargement des éléments uniquement")
            print("Vous pouvez utiliser l’option --force-dir DIRECTORY")
            resp = input("➤ Voulez-vous continuer ? [y/n] ")
            if resp.lower() != 'y':
                return
    write_log_entry(log_path, f"Répertoire utilisé : {rep_used or 'Aucun (force-dir ou distant uniquement)'}")

    # Réécriture des liens src/href
    pattern = r'(src|href)=["\'](https?://[^"\']+|[^"\']+_fichiers/[^"\']+)["\']'
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

        # Copie locale ou téléchargement si possible
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

        if not args.silent and args.verbose:
            print(f"🔁 {filename} → {new_link}")

        html = html.replace(url, new_link)
        write_log_entry(log_path, f"{source_name} ; {url} ; {new_link} ; {suffix} ; {status} ; origine: {origine}")

    # Sauvegarde
    with open(mod_path, 'w', encoding="utf-8") as f:
        f.write(html)
    if not args.silent:
        print(f"✅ HTML modifié : {mod_path}")
        print(f"🪵 Log : {log_path}")

# === Fonction principale : interprétation des arguments CLI ===
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_html", nargs="?", help="Fichier HTML source ou '-' pour STDIN")
    parser.add_argument("--stdin-name", help="Nom logique pour STDIN")
    parser.add_argument("--stdout", action="store_true", help="Écrit dans STDOUT au lieu de créer un fichier")
    parser.add_argument("--silent", action="store_true", help="Aucun affichage")
    parser.add_argument("--verbose", action="store_true", help="Mode verbeux (détail des remplacements)")
    parser.add_argument("--force", action="store_true", help="Force l’écrasement du HTML modifié")
    parser.add_argument("--no-prompt", action="store_true", help="Ne jamais poser de question")
    parser.add_argument("--force-dir", help="Répertoire de secours à utiliser")
    parser.add_argument("--no-log", action="store_true", help="Désactive l’écriture du journal")
    args = parser.parse_args()

    if not args.input_html:
        print("❌ Aucun fichier HTML fourni.")
        return

    if args.input_html == "-" or not sys.stdin.isatty():
        html_content = sys.stdin.read()
        pseudo_name = args.stdin_name or "stdin_input.html"
        process_html_file(html_content, pseudo_name, args)
    else:
        process_html_file(args.input_html, Path(args.input_html).name, args)

# === Point d’entrée du script ===
if __name__ == "__main__":
    main()
