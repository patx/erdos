#!/usr/bin/env python3
"""Render boot backgrounds using the supplied ErdOS logo (Pillow, build host only)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parent.parent
fontroot = Path('/usr/share/fonts/truetype/dejavu')
source = Image.open(root / 'branding/erdos-logo.png').convert('RGB')
# Ignore the source image's black margins; retain the actual supplied lettering.
mask = source.convert('L').point(lambda value: 255 if value > 60 else 0)
logo = source.crop(mask.getbbox())


def render(width, height, path):
    scale = 3
    factor = width / 800
    image = Image.new('RGB', (width * scale, height * scale), '#000000')
    draw = ImageDraw.Draw(image)
    logo_width = round(400 * factor * scale)
    logo_height = round(logo.height * logo_width / logo.width)
    mark = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
    image.paste(mark, ((image.width - logo_width) // 2, round(82 * factor * scale)))
    for y, value, size, color in [
        (188, 'A minimal Wayland desktop.', 22, '#f5f5f5'),
        (226, 'Built on Debian 13 · amd64', 16, '#aaaaaa'),
    ]:
        font = ImageFont.truetype(str(fontroot / 'DejaVuSans.ttf'), round(size * factor * scale))
        box = draw.textbbox((0, 0), value, font=font)
        draw.text(((image.width - box[2]) // 2, y * factor * scale), value, font=font, fill=color)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.resize((width, height), Image.Resampling.LANCZOS).save(path, optimize=True)


render(640, 480, root / 'config/bootloaders/syslinux_common/splash.png')
render(800, 600, root / 'config/bootloaders/grub-pc/splash.png')
render(800, 600, root / 'config/includes.chroot/usr/share/erdos/grub/boot.png')
