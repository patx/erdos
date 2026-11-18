# Build and customize ErdOS

## Supported host

Use Debian 13 (Trixie), amd64, on a Linux filesystem supporting executable bits,
symlinks and normal Unix ownership. Allow at least 20 GB free per build and several
GB of RAM. This is a planning allowance, not a measured minimum. Internet access
is required. Building uses root for live-build’s chroot and mounts; it does not
write a USB device or repartition the host.

```sh
sudo apt update
sudo apt install live-build debootstrap xorriso squashfs-tools wget cpio file apt-utils ca-certificates git python3 gcc libc6-dev pkg-config libx11-dev libxrandr-dev meson ninja-build libxcomposite-dev libxdamage-dev libxext-dev libxfixes-dev libxft-dev libxrender-dev libxi-dev libxinerama-dev libgif-dev libjpeg-dev libpng-dev
sudo ./build.sh
```

Build logs and the configuration snapshot remain in `work/build-XXXXXXXX/`.
Successful output is `dist/erdos-build-XXXXXXXX.iso` and its `.sha256` sidecar.
Each run starts fresh. Source staging alone works without root:

```sh
./build.sh --prepare
```

Staging does not compile helpers, resolve packages, build an ISO or test booting.

## What the build does

1. Copy `config/` into a new work directory and stage the pinned Twig runtime and overview notices.
   Recreate Debian's stock BIOS binary symlinks in that snapshot; no absolute
   host symlinks or bootloader binaries are committed to the source repository.
2. Compile the three C helpers and pinned Skippy-XD. The overview uses a stripped,
   size-optimized Meson build with `skippy_chipmunk=disabled` and subproject
   downloads prohibited. A build record verifies the disabled-physics option
   and binary hash in the final ISO.
3. Configure live-build for Debian 13 amd64, BIOS/UEFI, common firmware, no APT
   recommendations, no graphical login manager and no Secure Boot.
4. Fetch the official `apt-mirror-setup` udeb using signed Debian APT metadata.
5. Build the live filesystem and integrate Debian’s text installer. Installation
   skips networking and mirror downloads; its finish hook installs the signed
   APT configuration from the image after GRUB has finished using USB packages.
   A late live-config component applies the same sources to live sessions; clock
   synchronization is enabled for booted systems, without installer network access.
6. Verify the actual final ISO's desktop configuration, embedded installer policy,
   pinned Twig and core-package retention, then copy the ISO and checksum into
   `dist/`. This checks the image itself rather than temporary build manifests.

Compiler headers and build tools stay on the host. Runtime helpers reuse existing
X11/RandR/XInput libraries. Twig and Skippy-XD are pinned under `vendor/` with their
upstream revisions and licenses. They require no build-time source fetch,
Snap or pip installation. The build never downloads the optional physics subproject. An ErdOS patch adds
`--paging-once` to the vendored Skippy source; its modified source hash is recorded
and verified along with the binary.

Package versions follow current Trixie repositories, so builds are not bit-for-bit
reproducible snapshots. Keep the exact configuration, package manifest and source
revision with a release. Checksums detect corruption but are not signatures.

## Configuration map

| Edit | Location |
| --- | --- |
| Distribution, architecture, live locale/timezone and boot arguments | `build.sh` |
| Desktop/system packages and common firmware | `config/package-lists/` |
| Installer defaults | `config/includes.installer/preseed.cfg` |
| Offline-install APT setup | `config/includes.chroot/usr/local/lib/erdos/configure-apt`, `config/includes.chroot/usr/local/share/erdos/apt/erdos.sources` |
| Shortcuts, workspaces and menu | `config/includes.chroot/etc/skel/.config/openbox/` |
| Settings app and user preference handling | `config/includes.chroot/usr/local/bin/erdos-settings`, `config/includes.chroot/usr/local/lib/erdos/settings.py` |
| Touchpad defaults | `config/includes.chroot/etc/X11/xorg.conf.d/90-openbox-touchpad.conf` |
| Swipe bindings and overview appearance | `config/includes.chroot/etc/erdos/gestures.conf`, `config/includes.chroot/etc/xdg/skippy-xd.rc` |
| Application menu and screenshot commands | `config/includes.chroot/usr/local/bin/` |
| Tiling/restore and automatic display layout | `helpers/` |
| Boot menu layouts | `config/bootloaders/` |

Edit source before starting a build. Work directories are snapshots and do not
follow later source changes. Keep destination disks, partitioning, credentials
and erase/write confirmations out of the production preseed.

The live session defaults to US English, a US keyboard and America/New_York.
The installer asks for its own language, keyboard and timezone settings.

## Firmware and installed size

Firmware is selected for common Intel, Realtek, Qualcomm-Atheros, Broadcom and
MediaTek Wi-Fi; Intel/AMD graphics; SOF audio; and CPU microcode. This does not
cover every device. Specialized firmware and proprietary drivers may need to be
installed separately. The kernel retains its normal drivers.

Size trimming omits most manuals, package documentation and non-English UI
translations while retaining copyright notices. To restore them on an installed
system, remove `/etc/dpkg/dpkg.cfg.d/01-minimal-docs` and reinstall the affected
packages. Run `sudo apt update` before adding software.

## Native helpers separately

Generated binaries are ignored by Git. To compile them without rebuilding an ISO,
use the Debian 13 amd64 host and compiler prerequisites above:

```sh
./scripts/build-helpers.sh
```

Output goes into `release-tools/`, including Skippy-XD and its build record; an
optional argument selects another output directory. The build script uses the
same compiler path for image binaries.

## Update an existing ErdOS installation

This optional script is for an existing Debian 13 amd64 Openbox desktop, not an
installer or a way to convert an arbitrary Linux distribution. Build the native
helpers first, then run as your desktop user:

```sh
./scripts/build-helpers.sh
./scripts/update-desktop.sh
```

It uses sudo, installs the current default apps, removes xterm, updates system
input/udev defaults, backs up and replaces your Openbox/login configuration,
and reloads the desktop. It also updates defaults for future accounts. Review
the script before running it on a customized installation. Backups are reported
under `~/openbox-config-backup-XXXXXXXX`. Log out of the console too, or reboot,
to apply group, touchpad and login changes. Gesture access is limited to touchpad
event nodes through logind/udev; the updater does not add users to the input group. A nonpersistent live session loses
updates on reboot. The script does not repartition disks or rewrite bootloaders.

## Failed builds

Inspect `configure.log`, `installer-download.log` and `build.log` in the retained
work directory. Interrupted builds can leave mounted filesystems. Run
`sudo lb clean --purge` inside that build directory and verify its mounts are gone
before deleting it. Do not recursively delete an active build chroot.

## Branding and upstream references

Pre-rendered boot PNGs are committed; normal ISO builds do not need Pillow.
Regenerate them with `python3 scripts/render-branding.py` after installing Pillow
and DejaVu fonts on a development host. The supplied source logo is under
`branding/`; preserve third-party notices when editing bootloader templates.

- [Debian Live customization](https://live-team.pages.debian.net/live-manual/html/live-manual/customizing-contents.en.html)
- [Debian Installer integration](https://live-team.pages.debian.net/live-manual/html/live-manual/customizing-installer.en.html)
- [Trixie live-build options](https://manpages.debian.org/trixie/live-build/lb_config.1.en.html)
- [Debian Installer preseed example](https://www.debian.org/releases/trixie/example-preseed.txt)

## Gesture defaults

`/etc/erdos/gestures.conf` contains the six swipe bindings, a movement
threshold of 120 libinput-normalized units and a 1.5:1 direction ratio. The
unprivileged `erdos-gesture session`
controller starts at Openbox login and reads a single touchpad directly through
libinput. A clear swipe fires once before finger release; small movements and
ambiguous diagonals are ignored. Changing direction or cancelling after an action
has fired does not undo it. Keep the finger count steady and lift the fingers
before repeating a swipe.

The controller reuses its X11 connection for workspace messages, window cycling
and overview queries. Keyboard commands use a private local socket to that same
controller. There is no Python process or command-line helper started per swipe,
no polling while idle, and no libinput-gestures/debug-events subprocess. Existing
libinput, X11, XTest and Python/GI libraries provide the runtime; python3-pyudev
tracks hardware changes. The libinput-tools and python3-libevdev packages are no
longer needed by gestures and are omitted from the new image.

The reader follows touchpad connection changes and login activity/lock state,
closes its input context when inactive, and stops when X closes. The udev rule
`71-erdos-touchpad-gestures.rules` grants active-user access only to touchpad event
nodes before systemd's seat rules. No keyboard access or input-group membership
is granted. Stopping or killing the controller closes its input descriptors;
there is no separate raw reader to leave behind.

Skippy-XD still runs only while the overview is open, with physics and animations
disabled. No idle overview daemon, compositor or animation service is added.
Defaults are in `/etc/xdg/skippy-xd.rc`; copy to
`~/.config/skippy-xd/skippy-xd.rc` to customize. Logs are
`~/.local/state/erdos/gestures.log` and `overview.log`.

Copy `/etc/erdos/gestures.conf` to `~/.config/erdos/gestures.conf` for overrides.
Set a binding to `none` to disable it; allowed action names are shown in the
shipped file. Distance values from 20 to 1000 and direction ratios from 1 to 3
are accepted. Restart with `erdos-gesture stop` then `erdos-gesture session`.
The old libinput-gestures configuration is no longer read; translate existing
custom bindings into the new format. Keyboard-only systems open no touchpad but
keep the controller available for Super+O and window commands.

## Offline installation and APT

Building still needs Internet access to fetch Debian packages. Installing the
completed ISO does not: netcfg is disabled, the no-network-driver fallback is
preseeded, NTP is skipped, and apt-setup is told not to use a network mirror or
contact security/update services. The local package pool remains usable for GRUB
until finish-install.

The installer hook `12erdos-apt` runs `/usr/local/lib/erdos/configure-apt` in-target
after Debian's `10apt-cdrom-setup` has disabled and refreshed its CD-only sources.
Online sources are deliberately absent during that refresh to prevent network
lookups and retries; GRUB can still use the local pool beforehand.
It copies the shipped Deb822 source file to `/etc/apt/sources.list.d/erdos.sources`,
replaces the installer's temporary traditional list with a pointer comment, and
removes the stock `debian.sources` file to avoid duplicate Debian entries. It
never downloads indexes or packages. The configured suites are trixie,
trixie-updates and trixie-security, with main and non-free-firmware, over HTTPS
and explicitly signed by Debian's installed archive keyring. Connect through
NetworkManager after boot and run `sudo apt update`.

This internal helper is for a fresh installation target, not a general updater
for customized third-party APT configurations. No extra runtime package or
background service is needed. Firmware/kernel support in the live image is
preserved; installer networking support is not required for disk installation.
