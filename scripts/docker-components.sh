#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
if [ "${1:-}" = --reuse ]; then
    apt-get install -y --no-install-recommends dpkg-dev python3 git
    package=(/project/dist/packages/erdos-labwc_*.deb)
    [ "${#package[@]}" -eq 1 ]
    python3 /project/scripts/build-debs.py --reuse-compositor "${package[0]}" --output /artifacts/packages
    exit
fi
read -r -a dependencies < /project/scripts/build-dependencies.txt
apt-get install -y --no-install-recommends dpkg-dev "${dependencies[@]}"
bash /project/scripts/build-helpers.sh /artifacts/compositor
python3 /project/scripts/build-debs.py --labwc-dir /artifacts/compositor --output /artifacts/packages
