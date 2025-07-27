# === File: oaistatic_mirror.py
# Version: 1.3.0
# Date: 2025-07-27 16:10:00 UTC
# Description: Importe les ressources Firefox (_fichiers), centralise les fichiers, remplace les chemins locaux, logue par fichier avec timestamp. Conformité Git-ready.

import os
import sys
import hashlib
import requests
import argparse
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime
import shutil

DEFAULT_REPOSIT = os.path.expanduser("~/Dev/documentation")
CDN_DIR = "cdn"
PERSISTENT_DIR = "persistent"
LOG_SUBDIR = ".log"
HTML_SUBDIR = "html"
FIREFOX_IMPORT_DIR = "firefox_imports"

VALID_DOMAINS = {
    "cdn.oaistatic.com": CDN_DIR,
    "persistent.oaistatic.com": PERSISTENT_DIR
}

HASH_FUNC = hashlib.md5
VERBOSE = False
DRY_RUN = False
ALLOW_MISSING_DIR = False
MANUAL_FIREFOX_DIR = None


def compute_hash(file_path):
    h = HASH_FUNC()
    with open(file_path, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()

def prepare_directories(base_dir):
    oaistatic_dir = os.path.join(base_dir, "oaistatic")
    if not os.path.exists(oaistatic_dir):
        print(f"Le répertoire {oaistatic_dir} n'existe pas.")
        sys.exit(1)

    for sub in [CDN_DIR, PERSISTENT_DIR, LOG_SUBDIR, HTML_SUBDIR, FIREFOX_IMPORT_DIR]:
        os.makedirs(os.path.join(oaistatic_dir, sub), exist_ok=True)
    return oaistatic_dir

def guess_firefox_folder(input_file):
    base = os.path.basename(input_file)
    if base.endswith(".html"):
        stem = base[:-5].replace(".", "_")
        return os.path.join(os.path.dirname(input_file), f"{stem}_fichiers")
    return input_file + "_fichiers"

def extract_firefox_folder(input_file):
    candidate = MANUAL_FIREFOX_DIR or guess_firefox_folder(input_file)
    if os.path.exists(candidate):
        return candidate
    if ALLOW_MISSING_DIR:
        return None
    choice = input(f"⚠️ Dossier Firefox '{candidate}' introuvable. Continuer sans ? (y/n) ").strip().lower()
    if choice != 'y':
        sys.exit(1)
    return None

def import_firefox_files(source_dir, dest_dir, log_lines):
    if not source_dir:
        return
    for root, _, files in os.walk(source_dir):
        for file in files:
            src = os.path.join(root, file)
            rel_path = os.path.relpath(src, source_dir)
            dest = os.path.join(dest_dir, rel_path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if not os.path.exists(dest):
                shutil.copy2(src, dest)
                log_lines.append(f"FICHIER IMPORTÉ : {rel_path}")

def rewrite_html_paths(soup, firefox_src_dir, firefox_dest_rel, log_lines):
    for tag in soup.find_all(True):
        for attr in ['src', 'href']:
            if tag.has_attr(attr):
                val = tag[attr]
                if firefox_src_dir and val.startswith(os.path.basename(firefox_src_dir) + "/"):
                    rel_path = val.split("/", 1)[-1]
                    new_path = f"oaistatic/{firefox_dest_rel}/{rel_path}"
                    tag[attr] = new_path
                    log_lines.append(f"CHEMIN RÉÉCRIT : {val} → {new_path}")

def generate_logfile(log_dir, output_html):
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    base = os.path.basename(output_html).replace(".html", "")
    return os.path.join(log_dir, f"{base}.{ts}.Log")

def process(input_file, base_dir):
    oaistatic_dir = prepare_directories(base_dir)
    firefox_src = extract_firefox_folder(input_file)
    firefox_dest_rel = os.path.join(FIREFOX_IMPORT_DIR, os.path.splitext(os.path.basename(input_file))[0])
    firefox_dest = os.path.join(oaistatic_dir, firefox_dest_rel)

    output_html = os.path.join(oaistatic_dir, HTML_SUBDIR, os.path.basename(input_file).replace(".html", "-mod.html"))
    log_file = generate_logfile(os.path.join(oaistatic_dir, LOG_SUBDIR), output_html)

    log_lines = []
    import_firefox_files(firefox_src, firefox_dest, log_lines)

    with open(input_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    rewrite_html_paths(soup, firefox_src, firefox_dest_rel, log_lines)

    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(str(soup))

    with open(log_file, 'w', encoding='utf-8') as log:
        for line in log_lines:
            log.write(line + "\n")

    print(f"✅ HTML modifié : {output_html}\n🪵 Log : {log_file}")

def show_help():
    print("""Usage : oaistatic_mirror.py [-r repo] [--firefox-dir chemin/] [--allow-missing-dir] fichier.html

Version : 1.3.0
Date    : 2025-07-27 16:10:00 UTC
But     : Importer et réécrire les fichiers Firefox pour centralisation et Git
Options :
  -r DIR                   Répertoire racine cible (par défaut : ~/Dev/documentation)
  --firefox-dir PATH       Spécifie manuellement le dossier *_fichiers/ de Firefox
  --allow-missing-dir      Continue même si le dossier *_fichiers est manquant
  -h, --help               Affiche cette aide
""")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-r', dest='repo_path', default=DEFAULT_REPOSIT)
    parser.add_argument('--firefox-dir', dest='manual_firefox_dir', default=None)
    parser.add_argument('--allow-missing-dir', action='store_true')
    parser.add_argument('input_html', nargs='?')
    parser.add_argument('-h', '--help', action='store_true')
    args = parser.parse_args()

    ALLOW_MISSING_DIR = args.allow_missing_dir
    MANUAL_FIREFOX_DIR = args.manual_firefox_dir

    if args.help or not args.input_html:
        show_help()
        sys.exit(0)

    REPOSIT = os.path.abspath(os.path.expanduser(args.repo_path))
    process(args.input_html, REPOSIT)
