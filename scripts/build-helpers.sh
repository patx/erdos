#!/bin/bash
# Compile on the supported target so generated binaries match the live image.
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ $# -le 1 ]] || { echo 'Usage: build-helpers.sh [OUTPUT_DIRECTORY]' >&2; exit 2; }
if [[ ${1:-} == --help ]]; then
    echo 'Usage: build-helpers.sh [OUTPUT_DIRECTORY] (default: release-tools/)'
    exit 0
fi
. /etc/os-release
[[ $ID == debian && $VERSION_ID == 13 ]] || { echo 'Build helpers on Debian 13 amd64 (see docs/building.md).' >&2; exit 1; }
[[ $(dpkg --print-architecture) == amd64 ]] || { echo 'An amd64 build host is required.' >&2; exit 1; }
for command in cc pkg-config meson ninja; do
    command -v "$command" >/dev/null || { echo "Missing dependency: $command (see docs/building.md)." >&2; exit 1; }
done
pkg-config --exists x11 xrandr xi || { echo 'Install libx11-dev, libxrandr-dev and libxi-dev.' >&2; exit 1; }
output_dir=${1:-$project_dir/release-tools}
mkdir -p "$output_dir"
temporary_dir=$(mktemp -d "$output_dir/.helpers-XXXXXXXX")
trap 'rm -rf -- "$temporary_dir"' EXIT
read -r -a link_flags <<< "$(pkg-config --cflags --libs x11 xrandr xi)"
for helper in erdos-window-layout erdos-displays erdos-touchpad; do
    cc -std=c11 -D_DEFAULT_SOURCE -Os -s -Wall -Wextra -Werror \
        "$project_dir/helpers/$helper.c" -o "$temporary_dir/$helper" "${link_flags[@]}"
done
# Build Skippy-XD from pinned source. No subproject downloads or physics library.
meson setup "$temporary_dir/skippy-build" "$project_dir/vendor/skippy-xd" \
    --prefix=/usr --sysconfdir=/etc --buildtype=minsize --strip \
    --wrap-mode=nodownload -Dskippy_chipmunk=disabled
meson compile -C "$temporary_dir/skippy-build" skippy-xd
DESTDIR="$temporary_dir/skippy-stage" meson install -C "$temporary_dir/skippy-build" --no-rebuild
install -m755 "$temporary_dir/skippy-stage/usr/bin/skippy-xd" "$output_dir/skippy-xd"
python3 - "$temporary_dir/skippy-build" "$output_dir" "$project_dir/vendor/skippy-xd/UPSTREAM" <<'PY'
import hashlib, json, pathlib, subprocess, sys
options = json.loads(subprocess.check_output(['meson', 'introspect', '--buildoptions', sys.argv[1]]))
assert next(option['value'] for option in options if option['name'] == 'skippy_chipmunk') == 'disabled'
output = pathlib.Path(sys.argv[2])
commit = next(line.split(': ', 1)[1] for line in pathlib.Path(sys.argv[3]).read_text().splitlines() if line.startswith('Commit: '))
record = {'source_commit': commit, 'erdos_source_sha256': hashlib.sha256((pathlib.Path(sys.argv[3]).parent / 'src/skippy.c').read_bytes()).hexdigest(), 'physics': 'disabled', 'buildtype': 'minsize', 'stripped': True,
          'sha256': hashlib.sha256((output / 'skippy-xd').read_bytes()).hexdigest()}
(output / 'skippy-xd.build.json').write_text(json.dumps(record, indent=2) + '\n')
PY
for helper in erdos-window-layout erdos-displays erdos-touchpad; do
    install -m755 "$temporary_dir/$helper" "$output_dir/$helper"
done
printf 'Native helpers and Skippy-XD (physics disabled): %s\n' "$output_dir"
