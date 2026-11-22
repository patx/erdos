#!/bin/sh
# Compatibility entry point: use the same configuration-preserving hosted updater.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec python3 "$project_dir/scripts/erdos-update.py" "$@"
