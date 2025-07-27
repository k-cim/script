# === File: oaistatic_mirror.py
# Version: 1.2.0
# Date: 2025-07-27 15:14:00 UTC
# Description: Télécharge les ressources de cdn/persistent.oaistatic.com à partir d'un HTML et les remplace par des chemins relatifs. Log structuré, renommage en cas de conflit, sortie standard possible, nom de sortie auto, mode verbeux et dry-run.
# Conforms to SBSRATE standards: -h, version, timestamp, logging, safe overwrite, stdout, verbose, simulation.

import os
import sys
import hashlib
import requests
import argparse
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime

DEFAULT_REPOSIT = os.path.expanduser("~/Dev/documentation")
CDN_DIR = "cdn"
PERSISTENT_DIR = "persistent"
LOG_REL_PATH = "oaistatic/oaistatic.log"

HASH_FUNC = hashlib.md5
VALID_DOMAINS = {
    "cdn.oaistatic.com": CDN_DIR,
    "persistent.oaistatic.com": PERSISTENT_DIR
}

REPOSIT = DEFAULT_REPOSIT
OAISTATIC_DIR = os.path.join(REPOSIT, "oaistatic")
LOG_FILE = os.path.join(REPOSIT, LOG_REL_PATH)

VERBOSE = False
DRY_RUN = False

def compute_hash(file_path):
    h = HASH_FUNC()
    with open(file_path, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()

def prepare_directories():
    if not os.path.exists(OAISTATIC_DIR):
        print(f"Le répertoire {OAISTATIC_DIR} n'existe pas.")
        sys.exit(1)
    for subdir in [CDN_DIR, PERSISTENT_DIR]:
        full_path = os.path.join(OAISTATIC_DIR, subdir)
        os.makedirs(full_path, exist_ok=True)

def download_with_conflict_resolution(url, sub_path):
    full_path = os.path.join(OAISTATIC_DIR, sub_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    if DRY_RUN:
        if VERBOSE:
            print(f"[SIMULATION] Téléchargement ignoré : {url} → {sub_path}")
        return sub_path, None

    response = requests.get(url, timeout=10)
    response.raise_for_status()
    new_hash = HASH_FUNC(response.content).hexdigest()

    if not os.path.exists(full_path):
        with open(full_path, 'wb') as f:
            f.write(response.content)
        if VERBOSE:
            print(f"[OK] Téléchargé : {url} → {sub_path}")
        return sub_path, None

    existing_hash = compute_hash(full_path)
    if existing_hash == new_hash:
        if VERBOSE:
            print(f"[SKIP] Identique déjà présent : {sub_path}")
        return sub_path, None

    base, ext = os.path.splitext(full_path)
    n = 1
    while True:
        alt_path = f"{base}-{n}{ext}"
        if not os.path.exists(alt_path):
            with open(alt_path, 'wb') as f:
                f.write(response.content)
            rel_alt = os.path.relpath(alt_path, OAISTATIC_DIR)
            if VERBOSE:
                print(f"[RENOMMÉ] Conflit → {rel_alt}")
            return rel_alt, os.path.basename(alt_path)
        n += 1

def extract_and_replace(html, input_path, output_path=None):
    with open(input_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    tag_attrs = {'script': 'src', 'link': 'href', 'img': 'src'}

    for tag, attr in tag_attrs.items():
        for el in soup.find_all(tag):
            if el.has_attr(attr):
                url = el[attr]
                parsed = urlparse(url)
                domain = parsed.netloc
                if domain in VALID_DOMAINS:
                    sub_path = parsed.path.lstrip('/')
                    local_dir = VALID_DOMAINS[domain]
                    full_sub_path = os.path.join(local_dir, sub_path)
                    try:
                        local_path, renamed = download_with_conflict_resolution(url, full_sub_path)
                        el[attr] = f"oaistatic/{local_path}"

                        with open(input_path, 'r', encoding='utf-8') as rf:
                            lines = rf.readlines()
                            for idx, line in enumerate(lines):
                                if url in line:
                                    count = line.count(url)
                                    for i in range(count):
                                        log_line = f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} ; {os.path.basename(input_path)} ; {url} ; {os.path.basename(output_path) if output_path else 'STDOUT'} ; ligne-{idx+1:06d}-{i+1:02d}"
                                        if renamed:
                                            log_line += f" ; FICHIER RENOMMÉ : {renamed}"
                                        with open(LOG_FILE, 'a', encoding='utf-8') as logf:
                                            logf.write(log_line + "\n")
                                    break
                    except Exception as e:
                        with open(input_path, 'r', encoding='utf-8') as rf:
                            lines = rf.readlines()
                            for idx, line in enumerate(lines):
                                if url in line:
                                    err_line = f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} ; {os.path.basename(input_path)} ; {url} ; {os.path.basename(output_path) if output_path else 'STDOUT'} ; ligne-{idx+1:06d}-00 ; ERREUR : {str(e).splitlines()[0]}"
                                    with open(LOG_FILE, 'a', encoding='utf-8') as logf:
                                        logf.write(err_line + "\n")
                                    print(f"❌ Erreur ligne {idx+1} : {line.strip()}")
                                    break
                        print(f"Erreur lors du traitement de {url} : {e}")

    html_output = str(soup)
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_output)
    else:
        print(html_output)

def show_help():
    print("""Usage : oaistatic_mirror.py [-r chemin_repo] [-v] [--dry-run] input.html [output.html|-]

But       : Télécharge les fichiers de cdn/persistent.oaistatic.com et modifie le HTML avec des chemins locaux.
Nom       : oaistatic_mirror.py
Version   : 1.3.0
Date      : 2025-07-27 15:14:00 UTC
""")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-r', dest='repo_path', default=DEFAULT_REPOSIT)
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('input_html', nargs='?')
    parser.add_argument('output_html', nargs='?')
    parser.add_argument('-h', '--help', action='store_true')
    args = parser.parse_args()

    VERBOSE = args.verbose
    DRY_RUN = args.dry_run

    if args.help or not args.input_html:
        show_help()
        sys.exit(0)

    REPOSIT = os.path.abspath(os.path.expanduser(args.repo_path))
    OAISTATIC_DIR = os.path.join(REPOSIT, "oaistatic")
    LOG_FILE = os.path.join(REPOSIT, LOG_REL_PATH)
    prepare_directories()

    in_file = args.input_html
    out_file = args.output_html

    if not os.path.exists(in_file):
        print(f"Fichier introuvable : {in_file}")
        sys.exit(1)

    if out_file is None:
        base, ext = os.path.splitext(in_file)
        out_file = f"{base}-mod{ext}"

    extract_and_replace(in_file, in_file, out_file if out_file != '-' else None)

    if out_file != '-' and not DRY_RUN:
        print(f"Traitement terminé. Fichier modifié : {out_file}")

