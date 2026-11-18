#!/bin/sh
# Stage overview license/provenance files, without running it.
set -eu
root=${1:?Usage: stage-gestures.sh TARGET_ROOT}
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
for project in skippy-xd; do
    install -Dm644 "$project_dir/vendor/$project/COPYING" "$root/usr/local/share/doc/$project/copyright"
    install -Dm644 "$project_dir/vendor/$project/UPSTREAM" "$root/usr/local/share/doc/$project/UPSTREAM"
done
