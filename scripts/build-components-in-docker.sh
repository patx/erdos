#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec python3 "$project_dir/scripts/run-workspace.py" --kind build --docker --publish-packages -- bash /project/scripts/docker-components.sh "$@"
