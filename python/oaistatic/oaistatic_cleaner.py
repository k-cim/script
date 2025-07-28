#!/usr/bin/python3

# === File: oaistatic_cleaner.py
# Version: 0.01.03
# Date: 2025-07-28 08:07:00 UTC
# Description: Clean ChatGPT-exported HTML. Pipe-friendly + supports --input/--output.
# Supports --strip-style and --aggressif cleanup levels.

import sys
import re
import argparse
from bs4 import BeautifulSoup, Comment

def clean_html(input_html, strip_style=False, aggressif=False):
    soup = BeautifulSoup(input_html, 'html.parser')

    # Remove <script>, <style>, <noscript>, <iframe>, <link>
    for tag in soup(['script', 'style', 'noscript', 'iframe', 'link']):
        tag.decompose()

    # Remove HTML comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Remove meta generator tags
    for meta in soup.find_all('meta'):
        if meta.get('name', '').lower() == 'generator':
            meta.decompose()

    # Remove OpenAI-style overlays and ghost elements
    for tag in soup.find_all():
        tag_str = (tag.get('id', '') + ' ' + ' '.join(tag.get('class', []))).lower()
        style_str = tag.get('style', '').lower()
        content = tag.get_text(strip=True).lower()

        if (
            'overlay' in tag_str or
            'backdrop' in tag_str or
            'popup' in tag_str or
            'headlessui' in tag_str or
            'ad' in tag_str
        ) and (
            content in ['', 'advertisement', 'sponsored'] or
            'display:none' in style_str or
            'visibility:hidden' in style_str or
            'z-index:9999' in style_str
        ):
            tag.decompose()

    # Remove empty divs/spans with ad/sponsor classes
    for tag in soup.find_all(['div', 'span']):
        tag_str = (tag.get('id', '') + ' ' + ' '.join(tag.get('class', []))).lower()
        if not tag.text.strip() and ('ad' in tag_str or 'sponsor' in tag_str or 'track' in tag_str):
            tag.decompose()

    if strip_style or aggressif:
        for tag in soup.find_all():
            if 'style' in tag.attrs:
                del tag['style']

    if aggressif:
        for tag in soup.find_all():
            # Remove data-* and on* attributes
            attrs_to_remove = [attr for attr in tag.attrs if attr.startswith('data-') or attr.startswith('on')]
            for attr in attrs_to_remove:
                del tag[attr]
        # Remove empty divs/spans even without suspicious classes
        for tag in soup.find_all(['div', 'span']):
            if not tag.text.strip() and not tag.find():
                tag.decompose()

    # Filter allowed tags and classes
    allowed_tags = {
        'html', 'head', 'body', 'title', 'meta',
        'div', 'span', 'p', 'pre', 'code', 'strong', 'em', 'table',
        'thead', 'tbody', 'tr', 'td', 'th', 'br'
    }
    allowed_classes = {
        'chat-export', 'message', 'author', 'content'
    }

    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            tag.decompose()
        elif 'class' in tag.attrs:
            tag_classes = set(tag['class'])
            if not tag_classes.intersection(allowed_classes):
                del tag['class']

    return soup.prettify(formatter="html")

def main():
    parser = argparse.ArgumentParser(description="Clean ChatGPT-exported HTML (oaistatic)")
    parser.add_argument('--input', help="Input HTML file (default: stdin)", default=None)
    parser.add_argument('--output', help="Output HTML file (default: stdout)", default=None)
    parser.add_argument('--strip-style', action='store_true', help="Remove all inline style attributes")
    parser.add_argument('--aggressif', action='store_true', help="Deep clean: removes data-*, onclick, empty tags")

    args = parser.parse_args()

    if args.input:
        with open(args.input, 'r', encoding='utf-8') as f:
            input_html = f.read()
    else:
        input_html = sys.stdin.read()

    cleaned = clean_html(input_html, strip_style=args.strip_style, aggressif=args.aggressif)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(cleaned)
    else:
        sys.stdout.write(cleaned)

if __name__ == "__main__":
    main()

