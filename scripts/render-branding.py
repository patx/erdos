#!/usr/bin/env python3
"""Render boot and web assets from the supplied ErdOS wordmark with Pillow."""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
PAPER = '#f0edef'
source = Image.open(ROOT / 'branding/erdos-logo.png').convert('RGBA')
# Exclude nearly transparent stray pixels outside the wordmark.
bounds = source.getchannel('A').point(lambda opacity: 255 if opacity >= 24 else 0).getbbox()
if not bounds:
    raise ValueError('The ErdOS logo contains no visible pixels')
logo = source.crop(bounds)
red, green, blue, alpha = logo.split()
boot_logo = Image.merge('RGBA', (blue, green, red, alpha))


def splash(width, height, path):
    scale = 3
    canvas = Image.new('RGB', (width * scale, height * scale), '#000000')
    unit = width * scale / 800
    mark_width = round(400 * unit)
    mark_height = round(mark_width * logo.height / logo.width)
    mark = boot_logo.resize((mark_width, mark_height), Image.Resampling.LANCZOS)
    x = (canvas.width - mark_width) // 2
    y = round(87 * unit)
    pad_x = round(31 * unit)
    pad_y = round(17 * unit)
    ImageDraw.Draw(canvas).rounded_rectangle(
        (x - pad_x, y - pad_y, x + mark_width + pad_x, y + mark_height + pad_y),
        radius=round(12 * unit), fill=PAPER,
    )
    canvas.paste(mark, (x, y), mark)
    canvas.resize((width, height), Image.Resampling.LANCZOS).save(path, optimize=True)


splash(640, 480, ROOT / 'config/bootloaders/syslinux_common/splash.png')
splash(800, 600, ROOT / 'config/bootloaders/grub-pc/splash.png')
splash(800, 600, ROOT / 'config/includes.chroot/usr/share/erdos/grub/boot.png')

logo.save(ROOT / 'docs/assets/erdos-logo.png', optimize=True)
# Take the leading E from the wordmark for a legible square favicon.
icon = Image.new('RGBA', (128, 128))
ImageDraw.Draw(icon).rounded_rectangle((0, 0, 127, 127), radius=23, fill=PAPER)
letter = logo.crop((0, 0, round(logo.width * .244), logo.height))
letter.thumbnail((96, 96), Image.Resampling.LANCZOS)
icon.alpha_composite(letter, ((128 - letter.width) // 2, (128 - letter.height) // 2))
icon.resize((64, 64), Image.Resampling.LANCZOS).save(ROOT / 'docs/assets/favicon.png', optimize=True)
