#!/bin/bash
set -euo pipefail
[[ $# == 1 && $EUID == 0 ]] || { echo 'Usage: sudo fetch-installer-components.sh BUILD_DIRECTORY' >&2; exit 2; }
installer_build_dir=$1
[[ -d "$installer_build_dir/config" ]] || { echo 'Missing build configuration.' >&2; exit 1; }

# live-build excludes apt-mirror-setup by default. Supply the official udeb using
# its documented config/packages.binary mechanism. Keep APT's state isolated
# from the host; package hashes are checked against Debian's signed index.
installer_apt_dir=$(mktemp -d "$installer_build_dir/installer-apt-XXXXXXXX")
mkdir -p "$installer_apt_dir/lists/partial" "$installer_apt_dir/cache/archives/partial" "$installer_apt_dir/sourceparts" "$installer_apt_dir/preferencesparts"
printf '%s\n' 'deb [arch=amd64 signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] http://deb.debian.org/debian trixie main/debian-installer' > "$installer_apt_dir/sources.list"
installer_apt_options=(
  -o "Dir::Etc::sourcelist=$installer_apt_dir/sources.list"
  -o "Dir::Etc::sourceparts=$installer_apt_dir/sourceparts"
  -o 'Dir::Etc::preferences=/dev/null'
  -o "Dir::Etc::preferencesparts=$installer_apt_dir/preferencesparts"
  -o "Dir::State::lists=$installer_apt_dir/lists"
  -o "Dir::Cache=$installer_apt_dir/cache"
  -o 'APT::Sandbox::User=root'
  -o 'Acquire::Languages=none'
)
apt-get "${installer_apt_options[@]}" update
mkdir -p "$installer_build_dir/config/packages.binary"
cd "$installer_build_dir/config/packages.binary"
apt-get "${installer_apt_options[@]}" download apt-mirror-setup
