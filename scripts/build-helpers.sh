#!/bin/bash
# Build the pinned compositor; compiler dependencies never enter the image.
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ $# -le 1 ]] || { echo 'Usage: build-helpers.sh [OUTPUT_DIRECTORY]' >&2; exit 2; }
if [[ ${1:-} == --help ]]; then
    echo 'Usage: build-helpers.sh [OUTPUT_DIRECTORY]'; exit 0
fi
. /etc/os-release
[[ $ID == debian && $VERSION_ID == 13 ]] || { echo 'Build on Debian 13 amd64.' >&2; exit 1; }
output_dir=${1:-$project_dir/release-tools}
mkdir -p "$output_dir"
temporary_dir=$(mktemp -d "$output_dir/.labwc-XXXXXXXX")
trap 'rm -rf -- "$temporary_dir"' EXIT
cp -a "$project_dir/vendor/labwc" "$temporary_dir/source"
ln -s "$project_dir/vendor/wlroots" "$temporary_dir/source/subprojects/wlroots"
meson setup "$temporary_dir/build" "$temporary_dir/source" \
    --prefix=/usr/local --sysconfdir=/etc --buildtype=minsize --strip \
    --wrap-mode=nodownload --force-fallback-for=wlroots-0.19 \
    -Dman-pages=disabled -Dnls=disabled -Dtest=disabled -Dxwayland=enabled \
    -Dwlroots:examples=false -Dwlroots:renderers=gles2 -Dwlroots:backends=drm,libinput \
    -Dwlroots:color-management=disabled
meson compile -C "$temporary_dir/build" labwc
install -m755 "$temporary_dir/build/labwc" "$output_dir/labwc"
python3 - "$project_dir" "$output_dir" <<'PY'
import hashlib,json,pathlib,sys
root,out=map(pathlib.Path,sys.argv[1:])
record={'labwc':'0.9.7','wlroots':'0.19.2','buildtype':'minsize','xwayland':True,'effects':False,
        'sha256':hashlib.sha256((out/'labwc').read_bytes()).hexdigest()}
for project in ('labwc','wlroots'):
    digest=hashlib.sha256()
    for path in sorted((root/'vendor'/project).rglob('*')):
        if path.is_file():
            digest.update(str(path.relative_to(root/'vendor'/project)).encode()+b'\0'+path.read_bytes())
    record[project+'_source_sha256']=digest.hexdigest()
(out/'labwc.build.json').write_text(json.dumps(record,indent=2)+'\n')
PY
printf 'Pinned labwc with static wlroots: %s\n' "$output_dir"
