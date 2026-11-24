#!/bin/sh
# Keep VM disks, extracts and other disposable files in $ERDOS_TEST_DIR.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec python3 "$project_dir/scripts/run-workspace.py" --kind test -- "$@"
