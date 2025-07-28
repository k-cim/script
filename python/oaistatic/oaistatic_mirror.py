#!/usr/bin/python3
# === File: oaistatic_mirror.py
# Version: 1.3.5
# Date: 2025-07-28 20:13:50 UTC
# Description: Mirror remote assets (JS/CSS/media) from oaistatic/persistent/CDN into local folders,
#              update HTML paths, log actions with full trace. Force external_assets as fallback.
#              Includes options: --force-dir, --no-log, --verbose, --silent, --stdin, --stdout.
# Conforms to SBSRATE modular structure and CLI compatibility

import os
import re
import sys
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

# Configuration initiale (peut être extraite vers oaistatic.json à terme)
OAISTATIC_BASE = Path.home() / "Dev/documentation/oaistatic"
HTML_DIR = OAISTATIC_BASE / "html"
LOG_DIR = OAISTATIC_BASE / "_log"
CDN_DIR = OAISTATIC_BASE / "cdn/assets"
PERSISTENT_DIR = OAISTATIC_BASE / "persistent"
EXTERNAL_DIR = OAISTATIC_BASE / "external_assets"

ASSET_EXTENSIONS = [".js", ".css", ".svg", ".gif", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".m4v", ".woff", ".woff2", ".ttf"]

def slugify(text):
    return re.sub(r'[^a-z0-9\-_.]', '-', text.lower())

def md5sum(file_path):
    h = hashlib.md5()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def mirror_assets(soup, assets_dir, input_html, output_html, options):
    log_entries = []
    modified = False
    for idx, tag in enumerate(soup.find_all(['link', 'script', 'img', 'video', 'source'])):
        attr = 'href' if tag.name in ['link'] else 'src'
        url = tag.get(attr)
        if not url:
            continue

        # Extraction du nom de fichier
        filename = os.path.basename(url.split('?')[0])
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ASSET_EXTENSIONS:
            continue

        original_path = url
        media_type = ext[1:]

        # Tentative de récupération locale
        local_file = None
        if assets_dir:
            possible = assets_dir / filename
            if possible.exists():
                local_file = possible

        if not local_file:
            if "cdn.oaistatic.com" in url or "persistent.oaistatic.com" in url:
                local_file = CDN_DIR / filename
            elif url.startswith("http"):
                local_file = None
            else:
                local_file = assets_dir / filename if assets_dir else None
                if local_file and not local_file.exists():
                    local_file = None

        if local_file and local_file.exists():
            # Copier le fichier vers external_assets/
            dest_file = EXTERNAL_DIR / filename
            if not dest_file.exists() or md5sum(local_file) != md5sum(dest_file):
                EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
                dest_file.write_bytes(local_file.read_bytes())
                if options.verbose:
                    print(f"[✔] Copié : {local_file} → {dest_file}")
            new_path = f"../external_assets/{filename}"
            tag[attr] = new_path
            modified = True
            log_entries.append(f"{datetime.utcnow().isoformat()} ; {input_html.name} ; {original_path} ; {new_path} ; {media_type}")
        else:
            if options.verbose:
                print(f"[⚠] Fichier introuvable : {filename}")
    return log_entries, modified

def main():
    parser = argparse.ArgumentParser(description="Mirror remote assets into local directory and update HTML")
    parser.add_argument("html_file", nargs="?", help="HTML file to process")
    parser.add_argument("--force-dir", help="Force specific asset directory")
    parser.add_argument("--no-log", action="store_true", help="Disable logging")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--silent", action="store_true", help="Suppress all output")
    parser.add_argument("--stdin", action="store_true", help="Read HTML from stdin")
    parser.add_argument("--stdout", action="store_true", help="Write HTML to stdout")
    args = parser.parse_args()

    # Vérification des options conflictuelles
    if args.stdin and not sys.stdin.isatty():
        html_content = sys.stdin.read()
        input_path = Path("stdin_input.html")
    elif args.html_file:
        input_path = Path(args.html_file)
        if not input_path.exists():
            print(f"[❌] Fichier non trouvé : {input_path}")
            sys.exit(1)
        html_content = input_path.read_text(encoding="utf-8")
    else:
        print("[❌] Aucune source HTML fournie.")
        sys.exit(1)

    # Slugification du nom si caractères spéciaux
    original_name = input_path.stem
    slugified_name = slugify(original_name)
    if slugified_name != original_name:
        input_slugified = input_path.with_name(f"{slugified_name}{input_path.suffix}")
        if not args.silent:
            print(f"[ℹ] Slugifié : {input_path.name} → {input_slugified.name}")
    else:
        input_slugified = input_path

    # Détection du répertoire assets
    base_assets_name = f"{input_path.stem}_fichiers"
    assets_dir = Path(args.force_dir) if args.force_dir else input_path.parent / base_assets_name
    if not assets_dir.exists():
        if args.force_dir:
            if not args.silent:
                print(f"[⚠] Dossier forcé non trouvé : {assets_dir}")
        elif not args.silent:
            response = input(f"📁 Dossier Firefox non trouvé : {assets_dir}. Continuer ? (y/n) ")
            if response.strip().lower() != 'y':
                sys.exit(0)

    # Analyse du HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    log_entries, modified = mirror_assets(soup, assets_dir, input_path, input_slugified, args)

    # Sauvegarde HTML modifié
    if modified:
        HTML_DIR.mkdir(parents=True, exist_ok=True)
        output_html = HTML_DIR / f"{input_slugified.stem}-mod{input_slugified.suffix}"
        if args.stdout:
            print(str(soup))
        else:
            output_html.write_text(str(soup), encoding="utf-8")
            if not args.silent:
                print(f"✅ HTML modifié : {output_html}")

    # Log
    if not args.no_log:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.{input_path.name}.log"
        with log_file.open("w", encoding="utf-8") as log:
            log.write(f"{datetime.utcnow().isoformat()} ; Fichier analysé : {input_path.name} @ {datetime.utcfromtimestamp(input_path.stat().st_mtime).isoformat()}\n")
            if slugified_name != original_name:
                log.write(f"{datetime.utcnow().isoformat()} ; Slugification : {input_path.name} → {input_slugified.name}\n")
            log.write(f"{datetime.utcnow().isoformat()} ; Répertoire utilisé : {assets_dir} {'(forcé)' if args.force_dir else ''}\n")
            for entry in log_entries:
                log.write(entry + "\n")
        if not args.silent:
            print(f"🪵 Log : {log_file}")

if __name__ == "__main__":
    main()
