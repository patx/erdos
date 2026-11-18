#!/bin/sh
# Recreate Debian live-build's stock binary links only in the build snapshot.
set -eu
config=${1:?Usage: stage-bootloaders.sh CONFIG_DIRECTORY}
[ -d "$config/bootloaders" ] || { echo 'Missing bootloader configuration directory.' >&2; exit 1; }
while read -r relative target; do
    destination="$config/bootloaders/$relative"
    mkdir -p "$(dirname -- "$destination")"
    if [ ! -e "$destination" ] && [ ! -L "$destination" ]; then
        ln -s "$target" "$destination"
    fi
done <<'LINKS'
isolinux/isolinux.bin /usr/lib/ISOLINUX/isolinux.bin
isolinux/ldlinux.c32 /usr/lib/syslinux/modules/bios/ldlinux.c32
syslinux_common/libutil.c32 /usr/lib/syslinux/modules/bios/libutil.c32
syslinux_common/libmenu.c32 /usr/lib/syslinux/modules/bios/libmenu.c32
syslinux_common/vesamenu.c32 /usr/lib/syslinux/modules/bios/vesamenu.c32
syslinux_common/hdt.c32 /usr/lib/syslinux/modules/bios/hdt.c32
syslinux_common/libgpl.c32 /usr/lib/syslinux/modules/bios/libgpl.c32
syslinux_common/libcom32.c32 /usr/lib/syslinux/modules/bios/libcom32.c32
LINKS
