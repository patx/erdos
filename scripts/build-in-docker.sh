#!/bin/sh
# Root live-build work stays in a disposable Debian container's native filesystem.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec python3 "$project_dir/scripts/run-workspace.py" --kind build --docker --privileged --publish-iso --publish-packages -- bash /project/scripts/docker-build.sh
