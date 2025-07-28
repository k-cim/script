#!/usr/bin/python3
# === File: oaistatic_mirror.py
# Version: 1.3.2
# Date: 2025-07-27 23:59:00 UTC
# Description: Transforme un HTML Firefox offline en page locale autoportée (CSS, JS, images...) avec log détaillé, sans serveur local. Gère CDN, persistent et dossiers *_fichiers.

from datetime import datetime
import argparse
from pathlib import Path
from bs4 import BeautifulSoup
import shutil
import hashlib

OAISTATIC_BASE = Path.home() / "Dev/documentation/oaistatic"
HTML_DIR = OAISTATIC_BASE / "html"
LOG_DIR = OAISTATIC_BASE / "_log"
CDN_DIR = OAISTATIC_BASE / "cdn/assets"
PERSISTENT_DIR = OAISTATIC_BASE / "persistent"
EXTERNAL_DIR = OAISTATIC_BASE / "external_assets"

def compute_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def copy_with_dedup(source_file: Path, dest_dir: Path):
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / source_file.name
    if dest_file.exists():
        if compute_md5(dest_file) == compute_md5(source_file):
            return dest_file
        else:
            base, ext = source_file.stem, source_file.suffix
            i = 1
            while True:
                new_file = dest_dir / f"{base}_{i}{ext}"
                if not new_file.exists() or compute_md5(new_file) == compute_md5(source_file):
                    dest_file = new_file
                    break
                i += 1
    shutil.copy2(source_file, dest_file)
    return dest_file

def mirror_assets(soup, base_dir: Path, input_html: Path, firefox_assets: Path):
    log = []
    all_links = soup.find_all(
        lambda tag: any(attr in tag.attrs for attr in ["src", "href", "poster", "data-src"])
    )
    all_files = list(firefox_assets.rglob("*")) if firefox_assets.exists() else []

    for tag in all_links:
        for attr in ["src", "href", "poster", "data-src"]:
            if attr not in tag.attrs:
                continue
            original = tag[attr]
            if original.startswith("https://cdn.oaistatic.com/assets/"):
                filename = original.split("/")[-1]
                local_file = next((f for f in CDN_DIR.rglob(filename) if f.name == filename), None)
                if not local_file and firefox_assets:
                    local_file = next((f for f in all_files if f.name == filename), None)
                    if local_file:
                        local_file = copy_with_dedup(local_file, CDN_DIR)
                if local_file:
                    tag[attr] = f"../cdn/assets/{local_file.name}"
                    log.append(f"[CDN] {original} -> {tag[attr]}")
            elif original.startswith("https://persistent.oaistatic.com/"):
                subpath = original.replace("https://persistent.oaistatic.com/", "")
                dest_path = PERSISTENT_DIR / subpath
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                if not dest_path.exists():
                    log.append(f"[MISS] {original} -> NOT FOUND")
                tag[attr] = f"../persistent/{subpath}"
                log.append(f"[PERSISTENT] {original} -> {tag[attr]}")
            elif firefox_assets and firefox_assets.exists():
                filename = Path(original).name
                local_file = next((f for f in all_files if f.name == filename), None)
                if local_file:
                    copied = copy_with_dedup(local_file, EXTERNAL_DIR)
                    tag[attr] = f"../external_assets/{copied.name}"
                    log.append(f"[ASSET] {original} -> {tag[attr]}")
                else:
                    log.append(f"[MISS-LOCAL] {original} -> NOT FOUND")

    return log

def main():
    parser = argparse.ArgumentParser(description="Transforme une page HTML exportée par Firefox en fichier autonome local (CSS, JS, images).")
    parser.add_argument("html", help="Fichier HTML à transformer")
    parser.add_argument("--no-assets", action="store_true", help="Ne pas chercher de dossier *_fichiers associé")
    parser.add_argument("--assets-dir", help="Répertoire contenant les fichiers Firefox à utiliser (par défaut : <html>_fichiers)")
    args = parser.parse_args()

    input_html = Path(args.html).resolve()
    base_dir = input_html.parent
    filename = input_html.stem
    firefox_assets = Path(args.assets_dir) if args.assets_dir else base_dir / f"{filename}_fichiers"

    if not input_html.exists():
        print(f"❌ Fichier HTML non trouvé : {input_html}")
        return

    if not args.no_assets and not firefox_assets.exists():
        answer = input(f"📁 Dossier Firefox non trouvé : {firefox_assets}. Continuer ? (y/n) ")
        if answer.lower() != "y":
            return

    HTML_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    with open(input_html, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    log_entries = mirror_assets(soup, base_dir, input_html, firefox_assets)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    out_html = HTML_DIR / f"{filename}-mod.html"
    out_log = LOG_DIR / f"{timestamp}.{input_html.name}.log"

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(str(soup))

    with open(out_log, "w", encoding="utf-8") as f:
        f.write("\n".join(log_entries))

    print(f"✅ HTML modifié : {out_html}")
    print(f"🪵 Log : {out_log}")

if __name__ == "__main__":
    main()
