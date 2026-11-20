#!/bin/bash
# Run as your desktop user after extracting the project; system files use sudo.
set -euo pipefail
[[ $EUID != 0 ]] || { echo 'Run this script as your normal desktop user, without sudo.' >&2; exit 1; }
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source_dir="$project_dir/config/includes.chroot"
. /etc/os-release
[[ $ID == debian && $VERSION_ID == 13 && $(dpkg --print-architecture) == amd64 ]] || {
    echo 'This updater supports existing Debian 13 amd64 Openbox installations only.' >&2
    exit 1
}
for command in openbox; do
    command -v "$command" >/dev/null || { echo "Missing desktop component: $command" >&2; exit 1; }
done
for helper in erdos-window-layout erdos-displays erdos-touchpad skippy-xd; do
    [[ -x $project_dir/release-tools/$helper ]] || {
        echo 'Build the native helpers with ./scripts/build-helpers.sh first (see docs/building.md).' >&2
        exit 1
    }
done
[[ -f $project_dir/release-tools/skippy-xd.build.json ]] || { echo 'Rebuild native helpers before updating.' >&2; exit 1; }
sudo -v
if [[ -n ${DISPLAY:-} ]] && command -v erdos-gesture >/dev/null; then
    erdos-gesture stop
fi
# Mozilla's regular Firefox, with a repository-specific signing key.
sudo install -Dm644 "$source_dir/etc/apt/keyrings/packages.mozilla.org.asc" /etc/apt/keyrings/packages.mozilla.org.asc
sudo install -Dm644 "$source_dir/etc/apt/preferences.d/mozilla" /etc/apt/preferences.d/mozilla
sudo install -Dm644 "$source_dir/usr/local/share/erdos/apt/mozilla.sources" /etc/apt/sources.list.d/mozilla.sources
sudo apt-get update
sudo apt-get install -y --no-install-recommends desktop-file-utils hsetroot sakura firefox pcmanfm gvfs gvfs-backends gvfs-fuse openssh-client avahi-daemon \
    python3 python3-gi python3-pyudev gir1.2-gtk-3.0 gir1.2-gtksource-4 brightnessctl brightness-udev scrot x11-xserver-utils systemd-timesyncd bluez libspa-0.2-bluetooth
sudo systemctl enable --now systemd-timesyncd.service bluetooth.service
sudo bash "$project_dir/scripts/stage-twig.sh" /
sudo bash "$project_dir/scripts/stage-gestures.sh" /
sudo install -Dm755 "$source_dir/usr/local/bin/erdos-gesture" /usr/local/bin/erdos-gesture
sudo install -Dm644 "$source_dir/usr/local/lib/erdos/gesture_io.py" /usr/local/lib/erdos/gesture_io.py
sudo install -Dm644 "$source_dir/etc/erdos/gestures.conf" /etc/erdos/gestures.conf
sudo install -Dm644 "$source_dir/etc/xdg/skippy-xd.rc" /etc/xdg/skippy-xd.rc
sudo install -Dm644 "$source_dir/usr/lib/udev/rules.d/71-erdos-touchpad-gestures.rules" /usr/lib/udev/rules.d/71-erdos-touchpad-gestures.rules
sudo install -Dm755 "$source_dir/usr/local/bin/erdos-applications" /usr/local/bin/erdos-applications
sudo install -Dm755 "$source_dir/usr/local/bin/erdos-launch" /usr/local/bin/erdos-launch
sudo install -Dm644 "$source_dir/usr/local/lib/erdos/default_apps.py" /usr/local/lib/erdos/default_apps.py
sudo install -Dm644 "$source_dir/usr/local/lib/erdos/network_settings.py" /usr/local/lib/erdos/network_settings.py
sudo install -Dm755 "$source_dir/usr/local/bin/erdos-screenshot" /usr/local/bin/erdos-screenshot
sudo install -Dm755 "$source_dir/usr/local/bin/erdos-settings" /usr/local/bin/erdos-settings
sudo install -Dm644 "$source_dir/usr/local/lib/erdos/settings.py" /usr/local/lib/erdos/settings.py
sudo install -Dm644 "$source_dir/usr/local/lib/erdos/display_settings.py" /usr/local/lib/erdos/display_settings.py
sudo install -Dm644 "$source_dir/usr/local/lib/erdos/bluetooth_settings.py" /usr/local/lib/erdos/bluetooth_settings.py
sudo install -Dm644 "$source_dir/usr/share/applications/erdos-settings.desktop" /usr/share/applications/erdos-settings.desktop
sudo update-desktop-database /usr/local/share/applications
sudo apt-get remove -y chromium chromium-common chromium-sandbox
sudo install -Dm644 "$source_dir/usr/lib/udev/rules.d/91-erdos-keyboard-backlight.rules" /usr/lib/udev/rules.d/91-erdos-keyboard-backlight.rules
sudo usermod -aG video "$USER"
sudo udevadm control --reload-rules
sudo udevadm trigger --action=change --subsystem-match=input
sudo udevadm trigger --action=add --subsystem-match=backlight
sudo udevadm trigger --action=add --subsystem-match=leds --sysname-match='*::kbd_backlight'
backup_dir=$(mktemp -d "$HOME/openbox-config-backup-XXXXXXXX")
sudo install -Dm644 "$source_dir/usr/share/themes/ErdOS/openbox-3/themerc" /usr/share/themes/ErdOS/openbox-3/themerc
sudo install -Dm644 "$source_dir/etc/erdos-release" /etc/erdos-release
desktop_files=(.profile .config/gtk-3.0/settings.ini .config/openbox/rc.xml .config/openbox/menu.xml .config/openbox/autostart
    .config/pcmanfm/default/pcmanfm.conf .config/libfm/libfm.conf)
for relative in "${desktop_files[@]}"; do
    if [[ -f $HOME/$relative ]]; then
        mkdir -p "$backup_dir/$(dirname "$relative")"
        cp -a "$HOME/$relative" "$backup_dir/$relative"
    fi
    file_mode=644
    [[ $relative != .config/openbox/autostart ]] || file_mode=755
    install -D -m"$file_mode" "$source_dir/etc/skel/$relative" "$HOME/$relative"
done
sudo install -D -m644 "$source_dir/etc/X11/xorg.conf.d/90-openbox-touchpad.conf" /etc/X11/xorg.conf.d/90-openbox-touchpad.conf
for relative in "${desktop_files[@]}"; do
    file_mode=644
    [[ $relative != .config/openbox/autostart ]] || file_mode=755
    sudo install -D -m"$file_mode" "$source_dir/etc/skel/$relative" "/etc/skel/$relative"
done
# Seed new accounts without replacing the current user's existing associations.
sudo install -Dm644 "$source_dir/etc/skel/.config/mimeapps.list" /etc/skel/.config/mimeapps.list
if [[ -n ${DISPLAY:-} ]] && command -v erdos-displays >/dev/null; then
    erdos-displays --stop
fi
for helper in erdos-window-layout erdos-displays erdos-touchpad skippy-xd; do
    sudo install -D -m755 "$project_dir/release-tools/$helper" "/usr/local/bin/$helper"
done
sudo install -Dm644 "$project_dir/release-tools/skippy-xd.build.json" /usr/local/share/doc/skippy-xd/build.json
if [[ -n ${DISPLAY:-} ]]; then
    openbox --reconfigure
    erdos-settings --apply-session
    state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/erdos"
    mkdir -p "$state_dir"
    nohup pcmanfm --daemon-mode > "$state_dir/files.log" 2>&1 &
    nohup erdos-gesture session > "$state_dir/gestures.log" 2>&1 &
fi
printf 'Updated. Previous desktop configuration: %s\n' "$backup_dir"
echo 'Log out and log in again (or reboot) to apply touchpad and login-session defaults.'
echo 'If video-group membership was added, log out of the console too or reboot for brightness-key access.'
echo 'Live USB changes disappear after reboot unless persistence is configured.'
