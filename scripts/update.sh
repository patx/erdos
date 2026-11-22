#!/bin/sh
# Download first so a truncated pipe cannot execute a partial updater.
set -eu
update_temp=$(mktemp -d)
trap 'rm -rf "$update_temp"' EXIT HUP INT TERM
curl --proto '=https' --tlsv1.2 -fsSL --retry 3 \
    https://downloads.erd.sh/updates/erdos-update.py -o "$update_temp/erdos-update.py"
python3 "$update_temp/erdos-update.py" "$@"
