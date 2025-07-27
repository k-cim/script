# === File: inline_resources-0.01.00.py
# Version: 0.01.00
# Date: 2025-07-27 13:42:00 UTC
# Description: Inline local CSS into HTML for full offline rendering (PDF-like view).
# Conforms to strict modular structure + CLI compatibility.

import os
import argparse
from bs4 import BeautifulSoup

def inline_resources(input_file, output_file):
    base_dir = os.path.splitext(input_file)[0] + "_fichiers"

    with open(input_file, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # Inline all local CSS links
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href")
        if href and not href.startswith("http"):
            css_filename = os.path.basename(href)
            css_path = os.path.join(base_dir, css_filename)
            try:
                with open(css_path, "r", encoding="utf-8") as css_file:
                    style_tag = soup.new_tag("style")
                    style_tag.string = css_file.read()
                    link.replace_with(style_tag)
            except FileNotFoundError:
                print(f"[⚠️] CSS file not found: {css_path}")
                link.decompose()

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(str(soup))

    print(f"[✅] Offline HTML created: {output_file}")

def main():
    parser = argparse.ArgumentParser(
        description="📦 Inline local CSS into HTML for offline use / PDF-style rendering."
    )
    parser.add_argument("input", help="Input HTML file")
    parser.add_argument("output", help="Output standalone HTML file")
    parser.add_argument("-v", "--version", action="version", version="inline_resources 0.01.00 – 2025-07-27")

    args = parser.parse_args()
    inline_resources(args.input, args.output)

if __name__ == "__main__":
    main()

