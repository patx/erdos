#!/bin/bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
mode=${1:-build}
case "$mode" in
  build|--prepare) ;;
  -h|--help) echo 'Usage: sudo ./build.sh | ./build.sh --prepare'; exit 0 ;;
  *) echo "Unknown option: $mode" >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { echo 'Too many arguments' >&2; exit 2; }
if [[ $mode == build ]]; then
  [[ $EUID == 0 ]] || { echo 'Run with sudo on Debian 13 amd64.' >&2; exit 1; }
  . /etc/os-release
  [[ $ID == debian && $VERSION_ID == 13 ]] || { echo 'A Debian 13 build host is required.' >&2; exit 1; }
  [[ $(dpkg --print-architecture) == amd64 ]] || { echo 'An amd64 build host is required.' >&2; exit 1; }
  for command in lb debootstrap xorriso mksquashfs unsquashfs cc pkg-config file python3; do
    command -v "$command" >/dev/null || { echo "Missing dependency: $command (see README.md)" >&2; exit 1; }
  done
  if [[ -e $project_dir/.git ]]; then
    command -v git >/dev/null || { echo 'Git is required to verify a Git checkout (see README.md).' >&2; exit 1; }
  fi
fi
mkdir -p "$project_dir/work"
build_dir=$(mktemp -d "$project_dir/work/build-XXXXXXXX")
cp -a "$project_dir/config" "$build_dir/config"
bash "$project_dir/scripts/stage-bootloaders.sh" "$build_dir/config"
bash "$project_dir/scripts/stage-twig.sh" "$build_dir/config/includes.chroot"
bash "$project_dir/scripts/stage-gestures.sh" "$build_dir/config/includes.chroot"
printf 'Build directory: %s\n' "$build_dir"
if [[ $mode == --prepare ]]; then
  echo 'Customization files staged only; live-build was not invoked.'
  exit 0
fi
# Build-only dependencies stay on the host, outside the live filesystem.
bash "$project_dir/scripts/build-helpers.sh" "$build_dir/config/includes.chroot/usr/local/bin"
mkdir -p "$build_dir/config/includes.chroot/usr/local/bin" "$project_dir/release-tools"
for helper in erdos-window-layout erdos-displays erdos-touchpad skippy-xd; do
  cp "$build_dir/config/includes.chroot/usr/local/bin/$helper" "$project_dir/release-tools/$helper"
done
install -Dm644 "$build_dir/config/includes.chroot/usr/local/bin/skippy-xd.build.json" \
  "$build_dir/config/includes.chroot/usr/local/share/doc/skippy-xd/build.json"
cp "$build_dir/config/includes.chroot/usr/local/bin/skippy-xd.build.json" "$project_dir/release-tools/skippy-xd.build.json"
rm "$build_dir/config/includes.chroot/usr/local/bin/skippy-xd.build.json"
cd "$build_dir"
trap 'echo "Build failed; inspect $build_dir/configure.log, $build_dir/installer-download.log, $build_dir/build.log, and the retained build directory." >&2' ERR
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
  --debootstrap-options "--variant=minbase" \
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
mkdir -p "$project_dir/dist"
image="$project_dir/dist/erdos-${build_dir##*/}.iso"
cp live-image-amd64.hybrid.iso "$image"
(cd "$project_dir/dist" && sha256sum "${image##*/}" > "${image##*/}.sha256")
printf 'ISO: %s\nChecksum: %s.sha256\n' "$image" "$image"
