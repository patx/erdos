#!/bin/bash
# Internal disposable-container entry point.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
# Compiler and live-build dependencies stay in this automatically removed container.
read -r -a compiler_dependencies < /project/scripts/build-dependencies.txt
apt-get install -y --no-install-recommends live-build debootstrap xorriso squashfs-tools wget cpio file apt-utils "${compiler_dependencies[@]}"
python3 - <<'PY'
import shutil,sys
from pathlib import Path
sys.path.insert(0,'/project/scripts')
from project_files import public_files
source=Path('/project');target=Path('/tmp/erdos-project');target.mkdir()
for path in public_files(source):
    destination=target/path.relative_to(source)
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(path,destination)
PY
cd /tmp/erdos-project
./build.sh
cp dist/erdos-amd64.iso dist/erdos-amd64.iso.sha256 /artifacts/
