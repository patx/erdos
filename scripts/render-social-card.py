#!/usr/bin/env python3
"""Render the social preview from the project logo and desktop screenshot.

Development-only requirements: Pillow and DejaVu Sans fonts.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SCALE = 2
canvas = Image.new('RGB', (1200 * SCALE, 630 * SCALE), '#000000')
draw = ImageDraw.Draw(canvas)
fonts = Path('/usr/share/fonts/truetype/dejavu')

def text(position, value, size, color='#ffffff', bold=False):
    font = ImageFont.truetype(str(fonts / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')), size * SCALE)
    draw.text(tuple(int(v * SCALE) for v in position), value, font=font, fill=color, anchor='lt')

logo = Image.open(ROOT / 'docs/assets/erdos-logo.png').convert('RGBA')
alpha = logo.getchannel('A')
logo = ImageOps.invert(logo.convert('RGB')).convert('RGB', (
    .81, 0, .19, 0,
    .20, .80, 0, 0,
    0, 0, 1, 0,
))
logo.putalpha(alpha)
logo.thumbnail((250 * SCALE, 70 * SCALE), Image.Resampling.LANCZOS)
x, y = 64 * SCALE, 55 * SCALE
canvas.paste(logo, (x, y), logo)
text((64, 184), 'A minimal', 44, bold=True)
text((64, 244), 'Linux desktop.', 44, bold=True)
text((64, 338), 'Debian + Wayland', 24, '#b7d7f1')
text((64, 550), 'patx.gitman.io/erdos', 18, '#a2a8ad')
shot = Image.open(ROOT / 'docs/assets/live-window-overview.png').convert('RGB')
shot = shot.resize((590 * SCALE, round(590 * shot.height / shot.width) * SCALE), Image.Resampling.LANCZOS)
x, y = 555 * SCALE, 158 * SCALE
canvas.paste(shot, (x, y))
draw.rectangle((x, y, x + shot.width, y + shot.height), outline='#42474b', width=SCALE)
canvas.resize((1200, 630), Image.Resampling.LANCZOS).save(ROOT / 'docs/assets/og-image.png', optimize=True)
