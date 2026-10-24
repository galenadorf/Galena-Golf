"""Builds the app icons from brand/galena-crest.svg / .png: the crest centred on BG. Writes icon.svg, icon-192.png, icon-512.png,
icon-maskable-512.png (crest kept inside Android's central safe circle) and apple-touch-icon.png (180 px, iOS rounds the corners itself) in the repo root.
BG is also the manifest's theme_color / background_color and index.html's <meta name="theme-color">.
Usage: python icons.py   Needs Pillow (pip install pillow)."""
import os
import re

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BG = '#7A5354'
SVG = os.path.join(ROOT, 'brand', 'galena-crest.svg')
PNG = os.path.join(ROOT, 'brand', 'galena-crest.png')
VB = (394, 402)          # the crest's viewBox
ANY, MASK = .78, .58     # crest height as a share of the icon: full-bleed icons, and the maskable one (inside the safe circle)


def png(size, share, path):
    crest = Image.open(PNG).convert('RGBA'); h = round(size * share); w = round(h * crest.width / crest.height)
    crest = crest.resize((w, h), Image.LANCZOS)
    im = Image.new('RGBA', (size, size), BG); im.alpha_composite(crest, ((size - w) // 2, (size - h) // 2))
    im.convert('RGB').save(path, optimize=True)


def svg(path):
    inner = re.search(r'<svg[^>]*>(.*)</svg>', open(SVG, encoding='utf-8').read(), re.S).group(1)
    s = 512 * ANY / VB[1]; x, y = (512 - VB[0] * s) / 2, (512 - VB[1] * s) / 2
    open(path, 'w', encoding='utf-8').write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" fill="{BG}"/><g transform="translate({x:.1f} {y:.1f}) scale({s:.4f})">{inner}</g></svg>\n')


if __name__ == '__main__':
    for size, share, name in ((512, ANY, 'icon-512.png'), (192, ANY, 'icon-192.png'), (180, ANY, 'apple-touch-icon.png'), (512, MASK, 'icon-maskable-512.png')):
        png(size, share, os.path.join(ROOT, name))
    svg(os.path.join(ROOT, 'icon.svg'))
