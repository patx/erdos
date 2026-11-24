#!/bin/bash
# Internal worker: public build.sh provides the cleanup lifecycle.
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mode=${1:?Missing build mode}
build_dir=${ERDOS_WORK_DIR:?Use build.sh, not this internal worker directly}
cp -a "$project_dir/config" "$build_dir/config"
bash "$project_dir/scripts/stage-bootloaders.sh" "$build_dir/config"
bash "$project_dir/scripts/stage-twig.sh" "$build_dir/config/includes.chroot"
bash "$project_dir/scripts/stage-compositor.sh" "$build_dir/config/includes.chroot"
printf 'Temporary build directory: %s\n' "$build_dir"
if [[ $mode == --prepare ]]; then
  echo 'Customization staging check passed; temporary files will be removed.'
  exit 0
fi
# Build-only dependencies stay on the host, outside the live filesystem.
bash "$project_dir/scripts/build-helpers.sh" "$build_dir/config/includes.chroot/usr/local/bin"
install -Dm644 "$build_dir/config/includes.chroot/usr/local/bin/labwc.build.json" \
  "$build_dir/config/includes.chroot/usr/local/share/doc/labwc/build.json"
rm "$build_dir/config/includes.chroot/usr/local/bin/labwc.build.json"
cd "$build_dir"
lb config \
  --ignore-system-defaults \
  --mode debian \
  --distribution trixie \
  --architecture amd64 \
  --linux-flavours amd64 \
  --binary-image iso-hybrid \
  --bootloaders 'syslinux grub-efi' \
  --uefi-secure-boot disable \
  --debian-installer live \
  --debian-installer-gui false \
  --archive-areas 'main non-free-firmware' \
  --firmware-chroot false \
  --firmware-binary false \
  --apt-recommends false \
  --apt-indices false \
  --apt-source-archives false \
  --debootstrap-options "--variant=minbase --include=ca-certificates" \
  --security true \
  --updates true \
  --memtest none \
  --loadlin false \
  --win32-loader false \
  --iso-volume ERDOS \
  --iso-application "ErdOS Live" \
  --iso-publisher "ErdOS project" \
  --bootappend-live 'boot=live components username=user hostname=erdos noautologin locales=en_US.UTF-8 keyboard-layouts=us timezone=America/New_York' \
  2>&1 | tee configure.log
bash "$project_dir/scripts/fetch-installer-components.sh" "$build_dir" 2>&1 | tee installer-download.log
lb build 2>&1 | tee build.log
[[ -s live-image-amd64.hybrid.iso ]]
# Validate the actual final ISO: live-build can remove or relocate its temporary
# binary/ tree. A utility present live must also survive disk installation.
python3 "$project_dir/scripts/prepare-release.py" --verify-only --iso "$build_dir/live-image-amd64.hybrid.iso"
# The outer lifecycle publishes only after this worker and verification succeed.
mv live-image-amd64.hybrid.iso erdos-amd64.iso
sha256sum erdos-amd64.iso > erdos-amd64.iso.sha256
