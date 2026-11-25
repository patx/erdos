#!/bin/sh
# Install the pinned, MIT-licensed Twig runtime into a staging root.
set -eu
root=${1:?Usage: stage-twig.sh TARGET_ROOT}
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
source_dir="$project_dir/vendor/twig"
install -Dm755 "$source_dir/twig.py" "$root/usr/bin/twig"
install -Dm644 "$source_dir/twig.desktop" "$root/usr/share/applications/twig.desktop"
install -Dm644 "$source_dir/LICENSE" "$root/usr/share/doc/twig/copyright"
install -Dm644 "$source_dir/UPSTREAM" "$root/usr/share/doc/twig/UPSTREAM"
for size in 16 24 32 48 64 128 256 512; do
    install -Dm644 "$source_dir/icons/hicolor/${size}x${size}/apps/twig.png" \
        "$root/usr/share/icons/hicolor/${size}x${size}/apps/twig.png"
done
