# === File: oaistatic_mirror.py
# Version: 1.3.1
# Date: 2025-07-27 20:04:52 UTC
# Description: Analyse et traitement des ressources HTML locales issues de Firefox.
#              Détection automatique du dossier *_fichiers associé, mise en cache unifiée des assets,
#              remplacement des chemins par des liens relatifs, gestion de logs détaillés.
#              Conçu pour automatiser l'intégration et la visualisation offline de contenus web.

import argparse
import os
import sys
import re
import hashlib
import shutil
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime

# Répertoire racine par défaut
DEFAULT_REPO = os.path.expanduser("~/Dev/documentation/oaistatic")

# Initialisation des chemins relatifs
CDN_DIR = "cdn"
PERSISTENT_DIR = "persistent"
EXTERNAL_DIR = "external_assets"
LOG_DIRNAME = "_log"
HTML_DIRNAME = "html"

# Extensions de fichiers à rechercher
ASSET_EXTENSIONS = [".js", ".css", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mov"]


def compute_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def ensure_directories(base_path):
    for d in [CDN_DIR, PERSISTENT_DIR, EXTERNAL_DIR, HTML_DIRNAME, LOG_DIRNAME]:
        path = os.path.join(base_path, d)
        os.makedirs(path, exist_ok=True)


def detect_firefox_dir(input_html):
    base = Path(input_html)
    folder_candidate = base.parent / f"{base.stem}_fichiers"
    return folder_candidate if folder_candidate.exists() else None


def parse_args():
    parser = argparse.ArgumentParser(description="Mirror HTML resources locally for oaistatic.com and persistent.oaistatic.com")
    parser.add_argument("input_html", help="HTML file to process")
    parser.add_argument("output_html", nargs="?", help="Modified HTML output file")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="Target root repository (default: ~/Dev/documentation/oaistatic)")
    parser.add_argument("--force-no-dir", action="store_true", help="Bypass automatic *_fichiers directory detection")
    return parser.parse_args()


def mirror_assets(soup, base_dir, html_name, firefox_assets):
    log_entries = []
    lines = Path(html_name).read_text(encoding="utf-8").splitlines()
    replaced_files = {}
    
    for tag in soup.find_all(["script", "link", "img"]):
        attr = "src" if tag.name != "link" else "href"
        url = tag.get(attr)
        if not url:
            continue

        if url.startswith("https://cdn.oaistatic.com/"):
            relative_path = url.replace("https://cdn.oaistatic.com/", "")
            out_dir = os.path.join(base_dir, CDN_DIR, os.path.dirname(relative_path))
        elif url.startswith("https://persistent.oaistatic.com/"):
            relative_path = url.replace("https://persistent.oaistatic.com/", "")
            out_dir = os.path.join(base_dir, PERSISTENT_DIR, os.path.dirname(relative_path))
        elif firefox_assets:
            filename = Path(url).name
            local_file = next(f for f in firefox_assets.rglob(filename) if f.name == filename) if filename else None
            if local_file and local_file.exists():
                file_hash = compute_md5(local_file)
                new_name = f"{filename}"
                dest = os.path.join(base_dir, EXTERNAL_DIR, new_name)
                if os.path.exists(dest) and compute_md5(dest) != file_hash:
                    dest = os.path.join(base_dir, EXTERNAL_DIR, f"{file_hash}_{filename}")
                shutil.copy2(local_file, dest)
                tag[attr] = f"../{EXTERNAL_DIR}/{os.path.basename(dest)}"
                continue
            else:
                continue
        else:
            continue

        os.makedirs(out_dir, exist_ok=True)
        dest_file = os.path.join(out_dir, os.path.basename(relative_path))

        if not os.path.exists(dest_file):
            try:
                import requests
                r = requests.get(url)
                r.raise_for_status()
                with open(dest_file, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                log_entries.append(f"ERREUR : {url} => {e}")
                continue

        tag[attr] = os.path.relpath(dest_file, os.path.join(base_dir, HTML_DIRNAME))

    return log_entries


def main():
    args = parse_args()

    input_html = args.input_html
    output_html = args.output_html or str(Path(input_html).with_name(f"{Path(input_html).stem}-mod.html"))
    base_dir = os.path.abspath(args.repo)
    ensure_directories(base_dir)
    firefox_assets = None if args.force_no_dir else detect_firefox_dir(input_html)

    if not Path(input_html).exists():
        print(f"Fichier introuvable : {input_html}")
        sys.exit(1)

    if not Path(base_dir).exists():
        print(f"Dossier cible inexistant : {base_dir}")
        sys.exit(1)

    with open(input_html, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    log_entries = mirror_assets(soup, base_dir, input_html, firefox_assets)

    out_path = os.path.join(base_dir, HTML_DIRNAME, Path(output_html).name)
    log_name = f"{Path(output_html).stem}.{datetime.now().strftime('%Y%m%dT%H%M%S')}.log"
    log_path = os.path.join(base_dir, LOG_DIRNAME, log_name)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(str(soup))

    with open(log_path, "w", encoding="utf-8") as log:
        for entry in log_entries:
            log.write(entry + "\n")

    print(f"\n✅ HTML modifié : {out_path}\n🪵 Log : {log_path}")


if __name__ == "__main__":
    main()
