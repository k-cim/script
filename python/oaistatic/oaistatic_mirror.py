#!/usr/bin/python3
# === File: oaistatic_mirror.py
# Version: 1.3.3
# Date: 2025-07-28 15:20:00 UTC
# Description: Transforme un HTML avec dépendances locales Firefox en HTML propre, liens relatifs, dépendances vérifiées, MD5, ASCII-safe.
# Conforms to SBSRATE modular structure + CLI compatibility

import os
import sys
import argparse
import hashlib
import shutil
import re
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

# 📁 Répertoires cibles (bientôt dans oaistatic.json)
OAISTATIC_BASE = Path.home() / "Dev/documentation/oaistatic"
HTML_DIR = OAISTATIC_BASE / "html"
LOG_DIR = OAISTATIC_BASE / "_log"
CDN_DIR = OAISTATIC_BASE / "cdn/assets"
PERSISTENT_DIR = OAISTATIC_BASE / "persistent"
EXTERNAL_DIR = OAISTATIC_BASE / "external_assets"

# 🔧 Fonctions utilitaires
def slugify(name):
    # Supprime accents, majuscules, caractères spéciaux
    name = name.lower()
    name = re.sub(r'[éèêë]', 'e', name)
    name = re.sub(r'[àâä]', 'a', name)
    name = re.sub(r'[îï]', 'i', name)
    name = re.sub(r'[ôö]', 'o', name)
    name = re.sub(r'[ùûü]', 'u', name)
    name = re.sub(r'[^a-z0-9_.-]', '_', name)
    return name

def md5sum(filepath):
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def copy_with_md5(src, dst_dir):
    dst_dir.mkdir(parents=True, exist_ok=True)
    filename = slugify(src.name)
    dst = dst_dir / filename
    if dst.exists() and md5sum(dst) == md5sum(src):
        return dst
    shutil.copy2(src, dst)
    return dst

# 🔁 Traitement principal
def process_html(input_html, assets_dir, verbose=False, silent=False, to_stdout=False):
    input_path = Path(input_html).resolve()
    soup = BeautifulSoup(input_path.read_text(encoding="utf-8"), 'html.parser')

    assets_dir = Path(assets_dir) if assets_dir else input_path.with_name(input_path.stem + "_fichiers")
    if not assets_dir.exists():
        if not silent:
            print(f"📁 Dossier Firefox non trouvé : {assets_dir}. Continuer ? (y/n)", end=' ')
            if input() != 'y':
                return

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    logs = []

    for tag in soup.find_all(src=True) + soup.find_all(href=True):
        attr = "src" if tag.has_attr("src") else "href"
        val = tag[attr]

        if val.startswith("https://cdn.oaistatic.com/assets/"):
            fname = Path(val).name
            new = f"../cdn/assets/{fname}"
            tag[attr] = new
            logs.append((val, new, "cdn"))
        elif val.startswith("https://persistent.oaistatic.com/"):
            subpath = val.split("persistent.oaistatic.com/")[1]
            new = f"../persistent/{subpath}"
            tag[attr] = new
            logs.append((val, new, "persistent"))
        elif assets_dir and (assets_dir / Path(val).name).exists():
            src_file = next((p for p in assets_dir.rglob(Path(val).name)), None)
            if src_file:
                new_path = copy_with_md5(src_file, EXTERNAL_DIR)
                tag[attr] = f"../external_assets/{new_path.name}"
                ext = new_path.suffix.lower().lstrip('.')
                logs.append((val, str(tag[attr]), ext))

    out_file = HTML_DIR / (slugify(input_path.stem) + "-mod.html")
    out_file.write_text(str(soup), encoding="utf-8")

    if not silent and not to_stdout:
        print(f"✅ HTML modifié : {out_file}")

    log_path = LOG_DIR / f"{timestamp}.{slugify(input_path.name)}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as logf:
        for url, new, kind in logs:
            line = f"{datetime.utcnow().isoformat()} ; {input_path.name} ; {url} ; {new} ; {kind}"
            logf.write(line + "\n")

    if not silent and not to_stdout:
        print(f"🪵 Log : {log_path}")

    if to_stdout:
        print(str(soup))

# 🚀 Entrée principale
def main():
    parser = argparse.ArgumentParser(description="Transforme un HTML Firefox en version locale propre avec dépendances relatives.")
    parser.add_argument("html_file", nargs="?", help="Fichier HTML source à nettoyer.")
    parser.add_argument("--assets-dir", help="Répertoire contenant les fichiers liés (Firefox).")
    parser.add_argument("--verbose", action="store_true", help="Affiche les opérations détaillées.")
    parser.add_argument("--silent", action="store_true", help="Aucune sortie texte.")
    parser.add_argument("--stdin", action="store_true", help="Lecture depuis l'entrée standard.")
    parser.add_argument("--stdout", action="store_true", help="Écriture vers la sortie standard.")

    args = parser.parse_args()

    if args.stdin:
        html = sys.stdin.read()
        tmp = Path("/tmp/stdin_input.html")
        tmp.write_text(html, encoding="utf-8")
        process_html(tmp, args.assets_dir, verbose=args.verbose, silent=args.silent, to_stdout=args.stdout)
    else:
        if not args.html_file:
            print("❌ Fichier HTML requis sauf en mode --stdin.")
            return
        process_html(args.html_file, args.assets_dir, verbose=args.verbose, silent=args.silent, to_stdout=args.stdout)

if __name__ == "__main__":
    main()
