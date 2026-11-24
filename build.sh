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
  for command in umount lb debootstrap xorriso mksquashfs unsquashfs cc pkg-config file python3; do
    command -v "$command" >/dev/null || { echo "Missing dependency: $command (see README.md)" >&2; exit 1; }
  done
  if [[ -e $project_dir/.git ]]; then
    command -v git >/dev/null || { echo 'Git is required to verify a Git checkout (see README.md).' >&2; exit 1; }
  fi
fi
python3 "$project_dir/scripts/check-project.py"
if [[ $mode == --prepare ]]; then
  exec python3 "$project_dir/scripts/run-workspace.py" --kind prepare -- bash "$project_dir/scripts/build-image.sh" "$mode"
fi
exec python3 "$project_dir/scripts/run-workspace.py" --kind build --publish-iso -- bash "$project_dir/scripts/build-image.sh" "$mode"
