# Lean development ISO — 2026-11-24

Rebuilt the current checkout (`60df297` plus the `dev-lean` image label) from
scratch using the existing Debian 13 build environment, outside the shared
workspace filesystem. The final image verifier passes embedded configuration,
offline installer policy, package retention, compositor provenance, APT-cache
budget and root ownership/sudo setuid checks.

ISO SHA-256: `128fb9324f41a6934a9ab4751c970144ebba67bfe97dc8ad2fb043fe0b1f4efa`.
The ISO is local and unpublished; public Alpha 5 and its release metadata are
unchanged. Its six release artifacts are prepared separately from public
website release metadata.

A fresh offline UEFI installation completed on a new 24 GiB virtual disk with
manual disk prompts answered only in the private VM fixture. The installed disk
boots without installer media; console login starts labwc and its default
wallpaper. The normal account successfully authorized sudo. No applications
were opened before measurement. After a 120-second settle, five samples at
10-second intervals give **1.748 GiB installed and 353.2 MiB idle RAM**. The same
VM, sampler and console overhead were used for Alpha 5. Raw samples and exact
ISO identities are in [footprint.json](footprint.json).

Installed root used 1,876,951,040 bytes and EFI used
311,296 bytes. Swap was unused, with no cached APT
package indexes. NetworkManager and timesyncd were active; Bluetooth was inactive
without an adapter. PCManFM was absent from the idle process inventory. After
sampling, Super + E opened PCManFM; closing its window exited the process.
Installed-system checks confirm GVfs backends/FUSE, SSH/SFTP, Avahi and every
selected firmware/microcode package remain installed.

Exactly four packages were removed: nm-connection-editor, pulsemixer, libnma0
and libnma-common. None were added. The only version change is Firefox
160.0.1~build1 to 161.0~build1. Its retained files are 470,721 bytes smaller,
contributing about 0.45 MiB of the total 2.6 MiB disk saving; idle RAM is 16.6 MiB
lower. These are net build comparisons, not a claim that every difference comes
from a single change. Hardware/graphics configurations and later application
use can change memory consumption. Actual network-share connections, removable
hardware and physical GPU/touchpad operation were not retested by this offline VM.

# Current checkout: window-only overview and menu status

The current source removes the overview dock, its renderer/status timer and
Settings editor. Published Alpha 5 artifacts and the footprint results below
remain unchanged. A new local `dev-lean` ISO now includes these changes.

The pinned compositor compiles on Debian 13. A non-root headless Wayland session
exercises the actual compositor and GTK app together. Checks cover thirteen
Settings sections, `--time`/`--power` deep links reusing the existing window,
menu-editor preservation of the native rows, keyboard activation of both menu
actions, and opening/selecting/closing the dock-free overview. Menu placement
is after Settings and before Logout/Reboot/Power off.

Synthetic sysfs batteries are bound only inside a private test mount namespace.
Charging and discharging labels, percentage changes, absence, reappearance and
exclusion of peripheral batteries are exercised across repeated menu openings.
Rendered menus were reviewed with and without a system battery. Values refresh
on opening, with no status timer or subprocess. These checks do not certify a
physical laptop battery, touchpad or GPU. Source syntax, documentation links and
installer-policy checks pass. The menu/dock work added no package dependencies.

A subsequent source cleanup removes nm-connection-editor and pulsemixer from the
package list and PCManFM daemon mode from the default autostart. Build-time and
final-image guards reject the removed utilities. Source checks and `build.sh
--prepare` pass; staged configuration retains GVfs backends/FUSE, SSH/SFTP,
Avahi and all firmware/microcode selections. The new build and fresh-install
results are recorded above; Alpha 5 remains the published-image baseline.

# Alpha 5 ISO validation

The Alpha 5 amd64 ISO was rebuilt from source revision `a5779b4` in a Debian 13
KVM guest. The image verifier matched the embedded desktop and installer files
against source, checked the compositor provenance, and confirmed retention of
the required packages. All six release files, including the checksum
manifest, were prepared from that image and matched the files read back from
the Cloudflare download host.

A BIOS VM showed the blue boot logo and reached the offline installer's
language selection. A UEFI VM logged in to the Wayland live session, displayed
Dark Glacier as the default wallpaper, and opened the live overview dock and
Appearance settings. A later benchmark run on November 24, 2026 downloaded the
published ISO, verified SHA-256 against `release.json`, completed a fresh offline
UEFI install and booted the installed disk with no ISO attached. Console login
started labwc with Dark Glacier; the fresh account also successfully authorized
sudo. Physical hardware testing remains separate from these VM checks.

# Overview and Settings checks

Alpha 5 includes the configurable overview dock. Before the ISO build, source
syntax, documentation links and compositor compilation passed. The dock and
Settings work added no package dependencies.

A non-root, 1080p headless Wayland session tests the real Settings UI together
with the compiled compositor. It covers defaults, Apply/Revert, selected-row
sensitivity, the native installed-app chooser and cancel behavior, actual reordered
custom-launcher clicks with quoted percent/backslash/Unicode arguments, hiding the
dock and removing its hit targets, passive clock-only layouts and empty docks.
All fourteen sections are visited; labeled input accessibility, progress feedback,
small-window scrolling and native Adwaita dark/light rendering are checked.
An isolated settings-backend check covers malformed commands, launcher limits,
configuration round trips, backups and rejection of concurrent external edits.
These headless checks cover the UI and compositor, not physical input or GPU
behavior. The Alpha 5 image checks and fresh-install benchmark are recorded
separately.

# Alpha 4 validation

## Settings polish and desktop updater

The ISO selected unchanged for Alpha 4 retains Alpha 3’s package set, kernel, compositor and
verified offline installer. Its Settings UI/backend and development label are
updated, including the existing desktop portal’s light/dark preference; published
Alpha 3 assets remain unchanged. The package manifest is byte-for-byte identical
to Alpha 3. No dependencies or power-policy changes were introduced.

The GTK/labwc regression checks cover shortcut conflict rejection, real workspace
Apply/Revert, startup syntax safety, unsaved-edit close protection, stale refresh
suppression and display/refresh feedback. Screenshots are reviewed with existing
Adwaita themes. Hardware services are checked separately in a full live session;
an isolated container without those services is not proof of hardware operation.

The rebuilt development ISO passes a UEFI live boot and all 669 internal SHA-256
checks. All thirteen Settings sections load against the live session’s actual
services without section-load errors. Apply/Revert, unsaved-close protection,
shortcut validation and startup-file safety pass in that session too. A fresh
Firefox profile follows real portal preference changes: dark, light, then dark,
verified through website `prefers-color-scheme`. Existing browser/site overrides
can still take precedence.

The image verifier now checks root ownership of privileged system files and
sudo’s setuid bit. A deliberately broken cached extraction is rejected; the
final image passes, and passwordless live-session sudo works in the VM.

Physical audio-device volume/mute switching, Wi-Fi/Bluetooth hardware and display
hotplug still require laptop checks. Virtual null audio nodes did not retain
volume changes even outside Settings, so they are not accepted as proof of real
audio-volume operation. No fresh disk install or new footprint measurement was
performed for this Settings-only development image; the install and footprint
results below belong to the Alpha 3 baseline.

The user reports that the Settings image works on physical hardware. This does
not certify every hardware feature listed below. The selected ISO SHA-256 is
`3d979dd9d0c79233d657d5a65d9d140899d083c50db40077c1edc7affe7031e7`.
Its internal image version remains `dev-settings`; Alpha 4 is its public release
label. No ISO bytes are changed during release preparation.

Alpha 4 is published under `v1.0.0-alpha.4/`. The complete hosted ISO and all
five companion files were downloaded and verified against local SHA-256 hashes.
The GitHub prerelease and its source revision (`90d00e4`) were checked publicly.
The temporary upload Worker was removed after successful verification.

The hosted desktop updater is tested independently with an isolated filesystem:
successful installation and repeat execution, ordinary-user checks after an
update, rejection of locally modified files, path/symlink rejection, rollback
that protects later local fixes, and automatic recovery after a real write
failure. Driver, firmware, APT, power-policy and user-configuration sentinel
files remain unchanged throughout. Public bootstrap, Python helper, manifest and
bundle bytes match the tested local artifacts, and the live manifest hash
validates the downloaded bundle. An installed Wayland VM also downloads and
applies the hosted update as an ordinary user with sudo authorization. Its
pre-release image label is normalized to the supported Alpha 3 baseline before
that update test. Curl is absent from the minimal image; the documented Python
fallback downloads successfully without installing packages.

## Alpha 3 baseline validation

Alpha 3 uses labwc/Wayland. Alpha 2 remains available as the older Openbox/X11
release. The current local image identity is recorded in [release.json](release.json);
Alpha 4 preparation reuses the tested Settings image without rebuilding.

## Live overview source checks

The live overview was exercised in an isolated Wayland session on Intel
graphics. Tap Super to open and close it. Arrow keys show a white glow around
the selected live preview, and clicking a preview focuses its window. The dock
Wi-Fi button opens the Network tab and reuses the Settings window. Test
three-finger swipes again on physical hardware when validating a new image.

The remaining historical checks below describe Alpha 3/4, unless explicitly
marked Alpha 5. They do not certify every feature on the current ISO.

## Completed source and compositor checks

- Source syntax, local links, installer safety and public-file boundary pass.
- Pinned labwc 0.9.7 and static wlroots 0.19.2 build on Debian 13, stripped and
  size-optimized. Vulkan/examples/translations are disabled. The compiled
  compositor is approximately 6.5 MiB; this is not a complete-system measurement.
- A non-root, headless Wayland session starts without compositor configuration
  errors and displays native GTK windows with thumbnail previews.
- Super + O and Super alone open a persistent thumbnail grid; Escape dismisses.
  Root and Workspaces menus are captured and visually reviewed.
- Native snapping/maximizing then restoring returns the original client size.
- The standard workspace protocol confirms an initial two workspaces, creation
  of a spare when switching to the empty workspace and trimming on returning.
  Keyboard send/select actions retain occupied workspaces and create a spare.
- Input/gesture handling is native to the compositor. The old raw-device reader,
  access rule, Openbox, Skippy and X11-specific desktop helpers are removed.

## Image verification

The final-image verifier checks embedded configuration, offline installer policy,
required package retention, pinned Twig, compositor source/binary hashes and an
8 MiB ceiling on live-filesystem APT metadata/cache (downloaded DEBs are rejected).
The cache guard was verified against an oversized incremental build cache;
the clean final image passes it.
The image hook checks that all dynamic compositor libraries resolve and rejects
replaced desktop packages and full desktop environments. Build/checksum and VM
results for the current ISO are recorded below.

- All 669 internal SHA-256 entries pass on the Wayland candidate and release image.
- Alpha 3 changes only `/etc/erdos-release` in the measured candidate’s filesystem;
  its boot and offline-installer media are retained. The release-labeled image
  passes the configuration verifier and a full UEFI live boot.
- Full UEFI live-media boot reaches a clean console prompt; logging in starts labwc.
- Live shortcuts launch Sakura, regular Firefox, PCManFM and Twig. Super alone
  opens thumbnails showing all four; Escape dismisses.
- Print Screen writes a private PNG in `~/Pictures/Screenshots` using grim.
- A real Wayland output-mode change automatically restores after the 15-second
  confirmation timeout, including its original refresh rate.
- A fresh offline install completes with manual disk selection and final erase
  confirmation. The final image boots from its installed UEFI disk without
  installer media; console login starts the Wayland session.

## Limits

Headless tests are not physical touchpad/GPU tests. The MacBook and ASUS L203MA
still need checks of three/four-finger swipes, touchpad menu/middle-click, Wi-Fi,
Bluetooth, brightness, suspend/resume and monitor hotplug on the new image.
Shared-workspace behavior and output controls also need multi-monitor hardware
coverage. Alongside-OS partitioning and Secure Boot are not certified.

## Current footprint and earlier baselines

| Build | Installed disk | Idle RAM | Measured |
| --- | --- | --- | --- |
| Lean development ISO | 1.748 GiB | 353.2 MiB | 2026-11-24 |
| ErdOS 1 Alpha 5 | 1.751 GiB | 369.8 MiB | 2026-11-24 |
| Wayland candidate (Alpha 3) | 1.750 GiB | 355.4 MiB | 2026-11-21 |
| Previous X11 dev | 1.814 GiB | 361.8 MiB | 2026-11-21 |

Each is a fresh offline installation using UEFI, 2 vCPUs, 2 GiB RAM, a 24 GiB
install disk, an untouched 12 GiB spare and a 1280×800 virtio software-rendered
display. QEMU 10.0.13 uses KVM and the host CPU. No network/Bluetooth adapters,
package updates or application windows are present. The desktop stays active on
tty1 with its default background and the overview closed. Two console shells,
the serial getty and Python sampler are included. Alpha 5's serial getty was
started temporarily to match the previous setup; no persistent service policy
was changed.

RAM is MemTotal minus MemAvailable, not summed process RSS. All five Alpha 5
samples were 387,764,224 bytes after a 120-second settle, 10 seconds apart.
Disk is root plus EFI used filesystem blocks: 1,879,633,920 + 311,296 bytes,
excluding swap, filesystem free space and the spare disk. No cached APT package
indexes or swap use were reported. The kernel is `6.12.118+deb13-amd64`.

[Raw results](footprint.json) retain every sample, exact ISO checksum, filesystem
usage, service state and process inventory, including the older baselines.
The Alpha 5 digest matches [release.json](release.json); the measured ISO was not
rebuilt or modified. Physical GPU/driver/RAM configurations can change results.
The X11 comparison image is preserved locally as `dist/erdos-x11-dev.iso`.

## Reproduce the footprint measurement

Install the ISO offline into a disposable VM configured as above. Remove the
installer media, boot the installed disk and log in normally on tty1. Leave the
default desktop running without opening applications or the overview. Do not
run `apt update`, install packages or clear caches to improve the result.

Copy [measure-footprint.py](../scripts/measure-footprint.py) from this checkout
into the guest. Run it as the normal user from a separate virtual console,
then return the foreground display to the desktop while it samples:

```sh
python3 measure-footprint.py > footprint.json
```

It takes about 160 seconds, reads system state using Python's standard library
and existing system tools, and writes JSON. It requires no packages, root access
or background service. The reference run used the serial console for collection
and an additional idle tty2 shell; extra consoles and the sampler contribute to
RAM. Record the ISO checksum and VM details with each result. Copying the script
and output into the installed filesystem adds a few blocks, unlike the serial
stdin/output used in the reference run.

There is no screen locker bundled. Debian power policy remains unchanged;
no charging or idle-sleep daemon was added.
