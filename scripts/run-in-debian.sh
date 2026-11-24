#!/bin/sh
# Disposable container; only its own temporary workspace is writable on the host.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
privileged=
if [ "${1:-}" = --privileged ]; then privileged=--privileged; shift; fi
exec python3 "$project_dir/scripts/run-workspace.py" --kind test --docker ${privileged:+$privileged} -- "$@"
