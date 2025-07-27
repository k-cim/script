# === File: mirror_persistent_assets.py
# Version: 0.01.00
# Date: 2025-07-27 14:34:00 UTC
# Description: Download all assets from persistent.oaistatic.com and rewrite HTML to use local paths.
# Conforms to strict modular structure + CLI compatibility.

import os
import argparse
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

BASE_URL = "https://persistent.oaistatic.com/"
LOCAL_BASE = "persistent"  # local root directory

def save_remote_asset(url):
    rel_path = url.replace(BASE_URL, "")
    local_path = os.path.join(LOCAL_BASE, rel_path)

    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    try:
        print(f"⬇️  Downloading {url} → {local_path}")
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        with open(local_path, "wb") as f_out:
            f_out.write(r.content)
        return local_path
    except Exception as e:
        print(f"[⚠️] Failed to download {url}: {e}")
        return None

def patch_html_and_mirror(input_html, output_html):
    with open(input_html, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    tags = soup.find_all(attrs={"src": True}) + soup.find_all(attrs={"href": True})

    for tag in tags:
        attr = "src" if "src" in tag.attrs else "href"
        url = tag[attr]
        if url.startswith(BASE_URL):
            local_path = save_remote_asset(url)
            if local_path:
                tag[attr] = os.path.relpath(local_path, start=os.path.dirname(output_html))

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(str(soup))

    print(f"[✅] Local HTML written to: {output_html}")

def main():
    parser = argparse.ArgumentParser(
        description="📦 Mirror assets from persistent.oaistatic.com and rewrite HTML to use local paths."
    )
    parser.add_argument("input", help="Input HTML file")
    parser.add_argument("output", help="Output modified HTML file")
    parser.add_argument("-v", "--version", action="version", version="mirror_persistent_assets 0.01.00 – 2025-07-27")

    args = parser.parse_args()
    patch_html_and_mirror(args.input, args.output)

if __name__ == "__main__":
    main()

