#!/bin/bash
# Update an existing ErdOS installation; do not change a running compositor.
set -euo pipefail
[[ $EUID != 0 ]] || { echo 'Run as your desktop user, without sudo.' >&2; exit 1; }
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source_dir="$project_dir/config/includes.chroot"
. /etc/os-release
[[ $ID == debian && $VERSION_ID == 13 ]] || { echo 'Debian 13 is required.' >&2; exit 1; }
[[ -x $project_dir/release-tools/labwc && -f $project_dir/release-tools/labwc.build.json ]] || {
    echo 'Build the pinned compositor with scripts/build-helpers.sh first.' >&2; exit 1;
}
sudo -v
backup_dir=$(mktemp -d "$HOME/erdos-config-backup-XXXXXXXX")
for item in .profile .config/labwc .config/openbox .config/erdos; do
    if [[ -e $HOME/$item ]]; then
        mkdir -p "$backup_dir/$(dirname "$item")"
        cp -a "$HOME/$item" "$backup_dir/$item"
    fi
done
sudo install -Dm644 "$source_dir/etc/apt/keyrings/packages.mozilla.org.asc" /etc/apt/keyrings/packages.mozilla.org.asc
sudo install -Dm644 "$source_dir/etc/apt/preferences.d/mozilla" /etc/apt/preferences.d/mozilla
sudo install -Dm644 "$source_dir/usr/local/share/erdos/apt/mozilla.sources" /etc/apt/sources.list.d/mozilla.sources
sudo apt-get update
mapfile -t packages < <(sed -e '/^[[:space:]]*#/d' -e '/^[[:space:]]*$/d' "$project_dir/config/package-lists/desktop.list.chroot")
sudo apt-get install -y --no-install-recommends "${packages[@]}"
sudo cp -a "$source_dir/usr/local/." /usr/local/
sudo cp -a "$source_dir/usr/share/." /usr/share/
sudo install -Dm644 "$source_dir/usr/lib/systemd/user/erdos-background.service" /usr/lib/systemd/user/erdos-background.service
sudo install -Dm644 "$source_dir/etc/erdos/gestures.conf" /etc/erdos/gestures.conf
sudo install -Dm644 "$source_dir/etc/erdos-release" /etc/erdos-release
sudo install -Dm755 "$project_dir/release-tools/labwc" /usr/local/bin/labwc
sudo install -Dm644 "$project_dir/release-tools/labwc.build.json" /usr/local/share/doc/labwc/build.json
sudo bash "$project_dir/scripts/stage-twig.sh" /
sudo bash "$project_dir/scripts/stage-compositor.sh" /
sudo cp -a "$source_dir/etc/skel/." /etc/skel/
mkdir -p "$HOME/.config"
cp -a "$source_dir/etc/skel/.config/labwc" "$HOME/.config/"
cp "$source_dir/etc/skel/.profile" "$HOME/.profile"
# The old workspace-overview action has deliberately been retired.
if [[ -f $HOME/.config/erdos/gestures.conf ]]; then
    sed -i 's/workspace-overview/workspaces-menu/g' "$HOME/.config/erdos/gestures.conf"
fi
# Never remove the active X server or window manager mid-session.
echo "Updated. Backup: $backup_dir"
echo 'Log out of the desktop and console, then log in on tty1 to start labwc.'
echo 'After verifying labwc, old Openbox/Xorg packages may be removed separately.'
