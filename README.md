# ErdOS

A minimal **Debian 13 amd64** desktop using **labwc and Wayland**, with a small
application set, keyboard navigation and touchpad gestures.

**ErdOS 1 Alpha 5** introduces live window previews, a configurable overview dock,
improved Settings controls, blue boot branding and the Dark Glacier wallpaper.
[Download the amd64 ISO](https://downloads.erd.sh/v1.0.0-alpha.5/erdos-amd64.iso) ·
[SHA-256](https://downloads.erd.sh/v1.0.0-alpha.5/erdos-amd64.iso.sha256) ·
[Release notes](https://github.com/patx/erdos/releases/tag/v1.0.0-alpha.5).
This is an experimental prerelease; start in a VM. Secure Boot is not supported.

[Website](https://patx.gitman.io/erdos/) · [User guide](https://patx.gitman.io/erdos/guide.html) ·
[Build instructions](docs/building.md) · [Settings](docs/settings.md) ·
[Validation](docs/testing.md)

Existing Alpha 3 installations can use the [desktop updater](docs/updates.md)
without reinstalling or replacing machine-specific drivers and settings.

## Desktop

Alpha 5 includes the live overview and fourteen-section GTK Settings app. The
Alpha 4 ISO and hosted Alpha 3 desktop updater use the previous window switcher.

- Floating windows and square dark decorations. The dock appears only in the window overview.
- Native labwc overview with live window previews, a blurred desktop snapshot, and an app dock with Wi-Fi, a clock and battery status.
- Dynamic workspaces with one spare, shared across monitors, plus a Workspaces menu.
- One Python/GTK Settings window: defaults, input, shortcuts, menu, startup,
  displays, backgrounds, audio, networking, Bluetooth, battery and time.
- **Sakura**, **Firefox** (regular Mozilla release), **PCManFM** with USB/network
  support, and **Twig**. Menu entries and launch shortcuts follow selected defaults.
- Console login starts labwc. Logout returns to a clear login prompt.
- Debian's text installer works offline, sets signed APT sources and grants the
  first account sudo. Disk selection and erase/write approval stay manual.
- NetworkManager, PipeWire and BlueZ; common firmware. Debian power defaults.
- XWayland for legacy applications; GTK/wlroots portals for desktop integration.

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| Super + Enter / Ctrl + Alt + T | Default terminal |
| Super + B / E / T | Default browser / file manager / editor |
| Super + I | Settings |
| Super + Space / Menu | Desktop menu |
| Tap Super | Open or close the live window overview |
| Arrows + Enter | Select a window in the overview |
| Super + Shift + O | Workspaces menu |
| Super + Tab / Super + Shift + Tab | Cycle current-workspace windows |
| Ctrl + Super + Left / Right | Previous / next window directly |
| Super + Shift + 1–9 / Super + F1–F9 | Select an existing workspace |
| Ctrl + Shift + Super + 1–9 | Send window to an existing workspace |
| Super + Left / Right | Snap left / right |
| Super + Up / Down | Maximize / restore natural geometry |
| Super + Q / Alt + F4 | Close window |
| Super + H | Minimize window |
| Print / Alt + Print / Shift + Print | Desktop / focused window content / selected-area screenshot |

Numpad snapping shortcuts remain available. Screenshots save in
`~/Pictures/Screenshots`. Standard audio/brightness keys use PipeWire and
brightnessctl where supported. Fn mode is controlled by keyboard firmware.

## Touchpad and menu

| Gesture | Action |
| --- | --- |
| Three-finger tap / click | Desktop menu, including over applications |
| Three fingers up / down | Open / close the live window overview |
| Three fingers left / right | Previous / next window |
| Four fingers left / right | Next workspace (right) / previous workspace (left) |
| Four fingers up / down | Disabled by default; configurable |

Desktop right-click and Super + right-click also open the menu. In Settings →
Menu, change the three-finger and Super + right-click triggers independently.
The three-finger option replaces touchpad middle-click; disabling it restores
middle-click. Mouse middle-click is preserved. Swipe actions and sensitivity are
in Settings → Gestures. No raw-device gesture listener or polling daemon is used.

## Build

On Debian 13 amd64:

```sh
sudo apt update
sudo apt install live-build debootstrap xorriso squashfs-tools wget cpio file apt-utils
sudo apt install $(cat scripts/build-dependencies.txt)
sudo ./build.sh
```

The build compiles pinned labwc 0.9.7 and statically linked wlroots 0.19.2, keeps
build tools outside the image, and validates the finished ISO. Output is the
current `dist/erdos-amd64.iso` and its checksum; successful builds replace
that file. The previous X11 development image is preserved separately as
`dist/erdos-x11-dev.iso` for comparison and testing. Details and limitations are in [building.md](docs/building.md).

Test the live desktop and a disposable installation before using real disks.
Fresh offline VM measurement of the published Alpha 5 ISO on November 24, 2026
(2 vCPUs, 2 GiB RAM, 1280×800, software rendering):

| Build | Installed disk | Idle RAM |
| --- | --- | --- |
| ErdOS 1 Alpha 5 | 1.751 GiB | 369.8 MiB |

Disk includes root and EFI, excludes swap. RAM is the median of five
MemTotal-minus-MemAvailable samples after a two-minute settle, with the default
wallpaper active, overview closed and no app windows. Hardware results will
differ. [Raw measurements](docs/footprint.json) include the exact ISO checksum
and earlier baselines; [validation](docs/testing.md) explains how to reproduce
this measurement and records hardware-test limits.

ErdOS's own code is MIT-licensed. Vendored compositor/library/application sources
retain their licenses; see [THIRD_PARTY.md](THIRD_PARTY.md). Older versions live in
[Git history](https://github.com/patx/erdos/tags). Generated images, build state and
credentials are excluded from Git. Nothing is uploaded by the build scripts.
