#!/usr/bin/python3
# === File: oaistatic_mirror.py
# Version: 1.3.9
# Date: 2025-07-28 23:30:00 UTC
# Description: HTML localizer with asset separation (cdn, persistent, local). Rewrites links, copies assets, logs origin.
# Conforms to SBSRATE modular structure – DEV ONLY

import os
import re
import sys
import hashlib
import shutil
import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# === Configuration ===
VERSION = "1.3.9"
OAISTATIC_BASE = Path.home() / "Dev/documentation/oaistatic"
HTML_DIR = OAISTATIC_BASE / "html"
LOG_DIR = OAISTATIC_BASE / "_log"
EXTERNAL_DIR = OAISTATIC_BASE / "external_assets"
CDN_DIR = OAISTATIC_BASE / "cdn/assets"
PERSISTENT_DIR = OAISTATIC_BASE / "persistent"
EXTENSIONS = [".js", ".css", ".svg", ".webp", ".png", ".jpg", ".jpeg", ".gif", ".mp4", ".mov", ".ico"]

# === Slugify ===
def slugify(name):
    name = name.lower()
    name = re.sub(r"[^a-z0-9._-]", "-", name)
    name = re.sub(r"-+", "-", name)
    return name.strip("-._")

# === MD5 Checksum ===
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

    original_name = input_path.name
    slugified_name = slugify(original_name)
    slugified = slugified_name != original_name
    output_path = HTML_DIR / f"{slugified_name}-mod.html"
    input_slugified = output_path

    assets_dir = input_path.with_name(original_name.replace(".html", "_fichiers"))
    if args.force_dir:
        assets_dir = Path(args.force_dir)

    timestamp = datetime.utcnow().isoformat()
    log_entries = []

    with open(input_path, "r", encoding="utf-8") as f:
        html = f.read()

    # === Réécriture CDN ===
    cdn_matches = set(re.findall(r'https://cdn\.oaistatic\.com/assets/[^"\'\s)><]+', html))
    cdn_matches.update(re.findall(r'import\(["\'](https://cdn\.oaistatic\.com/assets/[^"\')]+)["\']\)', html))

    for url in sorted(cdn_matches):
        filename = url.split("/")[-1]
        dest_path = CDN_DIR / filename
        local_source = assets_dir / filename
        type_ = filename.split(".")[-1]

        # Copy si trouvé en local
        if local_source.exists():
            if not dest_path.exists() or md5sum(local_source) != md5sum(dest_path):
                CDN_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(local_source, dest_path)
                statut = "copié"
            else:
                statut = "identique – déjà présent"
            source_str = str(local_source)
        else:
            statut = "réécrit – distant (non trouvé localement)"
            source_str = url

        html = html.replace(url, f"../cdn/assets/{filename}")
        log_entries.append(f"{datetime.utcnow().isoformat()} ; {original_name} ; {source_str} ; ../cdn/assets/{filename} ; {type_} ; {statut} ; origine: cdn")

    # === Réécriture Persistent ===
    persistent_matches = set(re.findall(r'https://persistent\.oaistatic\.com/[^"\'\s)><]+', html))

    for url in sorted(persistent_matches):
        rel_path = url.split("persistent.oaistatic.com/")[-1]
        dest_path = PERSISTENT_DIR / rel_path
        local_source = assets_dir / Path(rel_path).name
        type_ = rel_path.split(".")[-1]

        if local_source.exists():
            if not dest_path.exists() or md5sum(local_source) != md5sum(dest_path):
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(local_source, dest_path)
                statut = "copié"
            else:
                statut = "identique – déjà présent"
            source_str = str(local_source)
        else:
            statut = "réécrit – distant (non trouvé localement)"
            source_str = url

        html = html.replace(url, f"../persistent/{rel_path}")
        log_entries.append(f"{datetime.utcnow().isoformat()} ; {original_name} ; {source_str} ; ../persistent/{rel_path} ; {type_} ; {statut} ; origine: persistent")

    # === Réécriture des liens locaux (_fichiers) ===
    local_matches = re.findall(rf'(["\'(]){re.escape(assets_dir.name)}/([^"\'\s)><]+)', html)

    for prefix, filename in sorted(set(local_matches)):
        src = f"{assets_dir.name}/{filename}"
        dest = f"../external_assets/{filename}"
        dest_path = EXTERNAL_DIR / filename
        local_source = assets_dir / filename
        type_ = filename.split(".")[-1]

        html = html.replace(src, dest)

        if local_source.exists():
            if not dest_path.exists() or md5sum(local_source) != md5sum(dest_path):
                EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(local_source, dest_path)
                statut = "copié"
            else:
                statut = "identique – déjà présent"
        else:
            statut = "introuvable – réécrit quand même"

        log_entries.append(f"{datetime.utcnow().isoformat()} ; {original_name} ; {src} ; {dest} ; {type_} ; {statut} ; origine: local")

    # === Sauvegarde HTML modifié ===
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    if not args.silent:
        print(f"✅ HTML modifié : {output_path}")

    # === Log ===
    if not args.no_log:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.{input_path.name}.log"
        with log_file.open("w", encoding="utf-8") as log:
            log.write(f"# === Script: oaistatic_mirror.py – Version: {VERSION} ===\n")
            log.write(f"{datetime.utcnow().isoformat()} ; Fichier analysé : {input_path.name} @ {datetime.utcfromtimestamp(input_path.stat().st_mtime).isoformat()}\n")
            if slugified:
                log.write(f"{datetime.utcnow().isoformat()} ; Slugification : {original_name} → {slugified_name}\n")
            log.write(f"{datetime.utcnow().isoformat()} ; Répertoire utilisé : {assets_dir.name} {'(forcé)' if args.force_dir else ''}\n")
            for entry in log_entries:
                log.write(entry + "\n")
        if not args.silent:
            print(f"🪵 Log : {log_file}")

# === Main ===
def main():
    parser = argparse.ArgumentParser(description="Localise les liens d'un HTML ChatGPT exporté")
    parser.add_argument("html_file", nargs="?", help="Fichier HTML à traiter (ou stdin)")
    parser.add_argument("--force-dir", help="Chemin vers le dossier de ressources (_fichiers)")
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
