# Changelog

## 1.0.0-alpha.1 — 2026-11-17

First alpha release of ErdOS.

### Menu and shortcut customization

- Add a Menu tab to edit, add, delete and reorder root Openbox menu entries.
- Add custom keyboard commands with conflict validation in Settings.
- Reverse default four-finger workspace swipes: left selects next, right selects previous.


### Desktop and installer

- Debian 13 amd64 live image with a panel-free Openbox desktop and text installation.
- Sakura, Chromium, PCManFM with USB/network support, and pinned Twig.
- Three-finger overview/window gestures and four-finger workspace gestures.
- Responsive threshold-based swipes through direct libinput/X11, with one action
  per swipe, no per-swipe helper processes and fewer runtime packages.
- On-demand Skippy-XD overview with physics and animations disabled; touchpad-only
  active-user access, hardware hotplug and login-session cleanup.
- Super+O overview fallback and Ctrl+Super+Left/Right direct window cycling.
- Dynamic workspaces, keyboard window tiling and exact geometry restoration.
- Screenshot, audio and brightness bindings; natural touchpad scrolling.
- Automatic monitor extension to the right, with the laptop primary.
- ErdOS branding for BIOS/UEFI boot menus and installed GRUB.
- Fully offline text installation without network-driver, DHCP, NTP or mirror
  questions. Signed APT sources are configured automatically for use after boot.
- Available firmware and first-account sudo defaults, with disk selection and
  erase/write approval kept interactive.
- Fixed missing sudo membership on installed accounts and scrot removal during
  installation; installed screenshot shortcuts passed VM checks.
- Public-source documentation, third-party notices and a static GitHub Pages site.

The November 17 image reuses the November 16 package base with updated desktop
configuration. Source, offscreen GTK, filesystem metadata and checksum checks
passed. This alpha still needs a fresh boot/install test; it is
published as a GitHub prerelease.

### Unified Settings

- Add the single-window ErdOS Settings app and Super+I shortcut, reusing Python/GTK and existing system services.
- Add a small XInput touchpad helper and live gesture configuration reload; no new runtime packages or settings daemon.
- Document controls, saved preferences and current limitations.

### Panel-free desktop and expanded Settings

- Remove tint2 and the tray applet; add Power and Date & Time sections.
- Add xrandr resolution selection with independent 15-second rollback and saved login modes.
- Add event-driven dynamic workspaces and configurable fixed counts in the existing listener.
- Add bare-Super window overview, Super+Shift+O workspace overview, Super+Space/Menu desktop menu, and workspace shortcuts through 9.
- Patch Skippy with a one-shot paging command, retaining disabled physics and no idle daemon.

### Time synchronization, APT and Bluetooth

- Enable systemd-timesyncd by default without adding an installer network step.
- Give live sessions the same signed HTTPS Debian sources as installed systems.
- Add native Bluetooth controls and pairing prompts to Settings, plus PipeWire Bluetooth audio support.
- Show automatic time-sync status and an enable action in Date & Time.
