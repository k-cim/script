# === File: mirror_oaistatic_js.py
# Version: 0.01.00
# Date: 2025-07-27 13:59:00 UTC
# Description: Download all JS from cdn.oaistatic.com and rewrite local HTML references.
# Conforms to strict modular structure + CLI compatibility.

import os
import argparse
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

def download_and_replace_js(input_html, output_html, js_dir="js"):
    os.makedirs(js_dir, exist_ok=True)

    with open(input_html, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    for script in soup.find_all("script", src=True):
        src = script["src"]
        if src.startswith("https://cdn.oaistatic.com/assets/"):
            filename = os.path.basename(urlparse(src).path)
            local_path = os.path.join(js_dir, filename)
            try:
                print(f"⬇️  Downloading {src} → {local_path}")
                r = requests.get(src, timeout=10)
                r.raise_for_status()
                with open(local_path, "wb") as f_out:
                    f_out.write(r.content)
                script["src"] = os.path.join(js_dir, filename)
            except Exception as e:
                print(f"[⚠️] Failed to download {src}: {e}")
                continue

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(str(soup))

    print(f"[✅] Output HTML written to: {output_html}")

def main():
    parser = argparse.ArgumentParser(
        description="📦 Mirror all JS from cdn.oaistatic.com/assets to local directory and patch HTML file."
    )
    parser.add_argument("input", help="Input HTML file")
    parser.add_argument("output", help="Output modified HTML file")
    parser.add_argument("-v", "--version", action="version", version="mirror_oaistatic_js 0.01.00 – 2025-07-27")
    args = parser.parse_args()

    download_and_replace_js(args.input, args.output)

if __name__ == "__main__":
    main()

