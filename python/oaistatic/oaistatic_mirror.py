#!/usr/bin/python3
# === File: oaistatic_mirror.py
# Version: 1.3.6
# Date: 2025-07-28 21:32:00 UTC
# Description: HTML localizer for ChatGPT-exported pages. Rewrites external links, copies assets, generates log.
# Conforms to SBSRATE modular structure – CLI friendly

import os
import re
import sys
import json
import hashlib
import shutil
import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# === Configuration (à terme via oaistatic.json) ===
OAISTATIC_BASE = Path.home() / "Dev/documentation/oaistatic"
HTML_DIR = OAISTATIC_BASE / "html"
LOG_DIR = OAISTATIC_BASE / "_log"
CDN_DIR = OAISTATIC_BASE / "cdn/assets"
PERSISTENT_DIR = OAISTATIC_BASE / "persistent"
EXTERNAL_DIR = OAISTATIC_BASE / "external_assets"

# === Extensions supportées ===
EXTENSIONS = [".js", ".css", ".svg", ".webp", ".png", ".jpg", ".jpeg", ".gif", ".mp4", ".mov", ".ico"]

# === Slugify basique ===
def slugify(name):
    name = name.lower()
    name = re.sub(r"[^a-z0-9._-]", "-", name)
    name = re.sub(r"-+", "-", name)
    return name.strip("-._")

# === Checksum ===
def md5sum(file):
    h = hashlib.md5()
    with open(file, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

# === Process HTML ===
def process_html(input_path, args):
    input_path = Path(input_path)
    if not input_path.exists():
        print(f"❌ Fichier introuvable : {input_path}")
        return

    stat = input_path.stat()
    date_mod = datetime.utcfromtimestamp(stat.st_mtime).isoformat()
    log_lines = []
    timestamp = datetime.utcnow().isoformat()

    # Slug + répertoire Firefox
    original_name = input_path.name
    slug_name = slugify(original_name)
    slugified = slug_name != original_name
    output_path = HTML_DIR / f"{slug_name}-mod.html"
    firefox_dir = input_path.with_name(original_name.replace(".html", "_fichiers"))

    # Cas --force-dir
    if args.force_dir:
        firefox_dir = Path(args.force_dir)

    # Journalisation initiale
    log_lines.append(f"{timestamp} ; Fichier analysé : {original_name} @ {date_mod}")
    if slugified:
        log_lines.append(f"{timestamp} ; Slugification : {original_name} → {slug_name}-mod.html")

    # Vérification dossier Firefox
    if firefox_dir.exists():
        log_lines.append(f"{timestamp} ; Répertoire utilisé : {firefox_dir.name}")
    else:
        log_lines.append(f"{timestamp} ; Répertoire introuvable : {firefox_dir.name}")
        if not args.force_dir:
            if not args.silent:
                proceed = input(f"\U0001F4C1 Dossier Firefox non trouvé : {firefox_dir.name}. Continuer ? (y/n) ")
                if proceed.lower() != "y":
                    return

    with open(input_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Réécriture des liens
    matches = re.findall(r'(https://cdn\.oaistatic\.com/assets/[^"\'\s>]+)', html)
    for idx, url in enumerate(matches):
        filename = url.split("/")[-1]
        dest = EXTERNAL_DIR / filename

        # Copie conditionnelle
        if firefox_dir.exists():
            media_file = firefox_dir / filename
            if media_file.exists():
                if not dest.exists() or md5sum(media_file) != md5sum(dest):
                    shutil.copy2(media_file, dest)
                type_ = filename.split(".")[-1]
                log_lines.append(f"{timestamp} ; {original_name} ; {media_file} ; ../external_assets/{filename} ; {type_}")

        html = html.replace(url, f"../external_assets/{filename}")

    # Sauvegarde HTML modifié
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    if not args.silent:
        print(f"✅ HTML modifié : {output_path}")

    # Sauvegarde log
    if not args.no_log:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / f"{timestamp.replace(':', '').replace('-', '').replace('.', '')}.{original_name}.log"
        with open(log_file, "w", encoding="utf-8") as f:
            for line in log_lines:
                f.write(line + "\n")
        if not args.silent:
            print(f"\U0001FA75 Log : {log_file}")

# === Main ===
def main():
    parser = argparse.ArgumentParser(description="Localise les liens d'un HTML ChatGPT exporté")
    parser.add_argument("html_file", nargs="?", help="Fichier HTML à traiter (ou stdin)")
    parser.add_argument("--force-dir", help="Chemin vers le dossier _fichiers à utiliser")
    parser.add_argument("--no-log", action="store_true", help="N'écrit pas de fichier de log")
    parser.add_argument("--silent", action="store_true", help="Aucune sortie console")
    parser.add_argument("--verbose", action="store_true", help="Affiche les opérations détaillées")
    args = parser.parse_args()

    if args.html_file:
        process_html(args.html_file, args)
    else:
        content = sys.stdin.read()
        temp_path = HTML_DIR / "stdin_input.html"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)
        process_html(temp_path, args)

if __name__ == "__main__":
    main()
