#!/usr/bin/env python3
"""Render the social preview from the project logo and desktop screenshot.

Development-only requirements: Pillow and DejaVu Sans fonts.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SCALE = 2
canvas = Image.new('RGB', (1200 * SCALE, 630 * SCALE), '#000000')
draw = ImageDraw.Draw(canvas)
fonts = Path('/usr/share/fonts/truetype/dejavu')

def text(position, value, size, color='#ffffff', bold=False):
    font = ImageFont.truetype(str(fonts / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')), size * SCALE)
    draw.text(tuple(int(v * SCALE) for v in position), value, font=font, fill=color, anchor='lt')

logo = Image.open(ROOT / 'docs/assets/erdos-logo.png').convert('RGB')
# Trim only the black canvas surrounding the supplied wordmark.
logo = logo.crop(logo.point(lambda p: 255 if p > 50 else 0).getbbox())
logo.thumbnail((250 * SCALE, 70 * SCALE), Image.Resampling.LANCZOS)
canvas.paste(logo, (64 * SCALE, 55 * SCALE))
text((64, 184), 'A minimal', 44, bold=True)
text((64, 244), 'Linux desktop.', 44, bold=True)
text((64, 338), 'ErdOS 1 Alpha 4', 24, '#1c9cff')
text((64, 384), 'Debian 13 + Wayland', 20, '#a2a8ad')
text((64, 550), 'patx.gitman.io/erdos', 18, '#a2a8ad')
shot = Image.open(ROOT / 'docs/assets/labwc-thumbnails.png').convert('RGB')
shot = shot.resize((590 * SCALE, round(590 * shot.height / shot.width) * SCALE), Image.Resampling.LANCZOS)
x, y = 555 * SCALE, 158 * SCALE
canvas.paste(shot, (x, y))
draw.rectangle((x, y, x + shot.width, y + shot.height), outline='#42474b', width=SCALE)
canvas.resize((1200, 630), Image.Resampling.LANCZOS).save(ROOT / 'docs/assets/og-image.png', optimize=True)
