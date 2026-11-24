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
Appearance settings. These checks covered VM boot and live use. Full disk
installation and physical hardware testing were outside this Alpha 5 run.

# Current development checks

The configurable overview dock is newer than the published Alpha 4 image. Source
syntax, documentation links and compositor compilation pass. No package-list
changes or new dependencies were introduced.

A non-root, 1080p headless Wayland session tests the real Settings UI together
with the compiled compositor. It covers defaults, Apply/Revert, selected-row
sensitivity, the native installed-app chooser and cancel behavior, actual reordered
custom-launcher clicks with quoted percent/backslash/Unicode arguments, hiding the
dock and removing its hit targets, passive clock-only layouts and empty docks.
All fourteen sections are visited; labeled input accessibility, progress feedback,
small-window scrolling and native Adwaita dark/light rendering are checked.
An isolated settings-backend check covers malformed commands, launcher limits,
configuration round trips, backups and rejection of concurrent external edits.
No ISO rebuild, fresh install or physical input/GPU certification was performed
for this development change. Hardware-dependent service checks below belong to
prior release validation, not this headless run.

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

The checks below record the previously published Alpha 4 image.

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

## Footprint comparison

| Build | Installed disk | Idle RAM |
| --- | --- | --- |
| Previous X11 dev | 1.814 GiB | 361.8 MiB |
| Wayland candidate (Alpha 3) | 1.750 GiB | 355.4 MiB |

Both are fresh offline installations with identical VM settings and default
services. The desktop is active, with no application windows opened before
measurement. Two console shells, the serial getty and the Python sampler are
included identically. RAM uses five samples after 120 seconds; disk excludes
swap. Both report no cached APT package indexes and no swap use.

[Raw results](footprint.json) identify each exact ISO, VM hardware, per-sample
memory values, used root/EFI blocks and service state. The X11 ISO is preserved
as `dist/erdos-x11-dev.iso`. Physical GPU/driver measurements can differ from
this software-rendered VM.

There is no screen locker bundled. Debian power policy remains unchanged;
no charging or idle-sleep daemon was added.
