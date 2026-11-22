#!/bin/sh
# Stage licenses for the pinned compositor and its statically linked library.
set -eu
root=${1:?Usage: stage-compositor.sh TARGET_ROOT}
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
for project in labwc wlroots; do
    install -Dm644 "$project_dir/vendor/$project/LICENSE" "$root/usr/local/share/doc/$project/copyright"
    install -Dm644 "$project_dir/vendor/$project/UPSTREAM" "$root/usr/local/share/doc/$project/UPSTREAM"
done
