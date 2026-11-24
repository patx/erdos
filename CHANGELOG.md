# ErdOS 1 Beta 1 — 2026-11-24

- Automatically clean build/test workspaces and owned processes/containers on
  exit, retain bounded latest logs and keep only the latest verified local ISO.
  Failed builds preserve that image; unrelated Docker/project data is untouched.
- Add disposable Debian build/test wrappers and document the storage policy.
  These are host tools only; no installed packages or runtime behavior change.

- Establish a Gitman labwc maintenance fork with upstream history, focused ErdOS
  commits and a pinned export/check helper. Document deliberate upstream updates
  and add an offline vendor-integrity check. Keep labwc 0.9.7, wlroots 0.19.2 and
  every byte of the existing vendored compositor source unchanged.

- Build and fresh-install test the local `dev-lean` ISO. Same-VM measurements:
  1.748 GiB installed and 353.2 MiB idle RAM, saving 2.6 MiB disk and 16.6 MiB RAM
  versus Alpha 5. Firefox is also updated to 161.0; about 0.45 MiB of disk saving
  comes from that version change. Beta 1 publishes this exact tested image without rebuilding it; its embedded
  version remains `dev-lean`.

- Remove nm-connection-editor and pulsemixer; Settings retains normal Wi-Fi and
  sound controls, with nmcli available for advanced connection profiles.
- Launch PCManFM only on demand rather than starting its daemon at login. Keep
  USB mounting, GVfs network backends, share discovery and SSH/SFTP transport.
  Automatic removable-drive mounting now requires an open file manager.

- Remove the overview dock, its renderer/status timer, launch helper and Settings
  tab. Keep the native live window overview and give its grid the freed space.
- Add a clickable 12-hour clock and battery percentage below Settings in the
  desktop menu, before Logout/Reboot/Power off. They open Date & Time and Power
  in the existing Settings window. Hide battery status when no system battery
  is available; refresh only when the menu opens. No new dependencies or daemon.
- Older Alpha 5 downloads remain available. The hosted updater is unchanged.

# ErdOS 1 Alpha 5 — 2026-11-23

- Add an Overview Dock tab: hide/show the dock, add/edit/remove/reorder launchers,
  choose installed applications and toggle launcher names, clock and battery.
- Keep default-program roles dynamic, preserve custom quoted arguments, and apply
  dock edits the next time the overview opens without a daemon or restart.
- Use native GTK layout, readable theme text, accessible input labels, keyboard
  focus, selected-row actions, progress feedback and inline validation throughout
  Settings. No packages, UI framework or background service are added.
- Rebuild the live ISO with the blue ErdOS boot logo and Dark Glacier as the
  bundled default wallpaper. Saved wallpaper and solid-color preferences take
  precedence.
- Refresh the website with the blue wordmark and new desktop screenshots.
- Published Alpha 4 artifacts and the hosted updater remain unchanged.

# ErdOS 1 Alpha 4 — 2026-11-22

## Settings and installed-system updates

- Hosted desktop updates preserve drivers, firmware, Debian packages and personal
  configuration, with local-change detection, backups and rollback.
- The first update brings the Settings polish to existing Alpha 3 installations.

- Keep Python/GTK 3 and the existing package set; no extra UI framework or daemon.
- Group controls, add Apply/Revert and unsaved-edit close protection, and make
  menu and shortcut editors readable.
- Match shortcut conflict checks to labwc’s case-insensitive keysyms and aliases.
- Load selected-device audio levels; refresh audio without reopening Settings.
- Discard stale asynchronous loads, separate refresh from save feedback, and
  refresh display choices after resolution trials with proper error reporting.
- Publish light/dark preference through the existing Settings portal so Firefox
  and supporting websites can follow the system appearance.
- Keep Debian power policy and published Alpha 3 assets unchanged.
- Select the existing hardware-tested ISO unchanged for Alpha 4; no rebuild.
  The ISO retains its internal `dev-settings` image label; public release metadata
  identifies it as `1.0.0-alpha.4`. The updater is hosted separately.

# ErdOS 1 Alpha 3 — 2026-11-21

Alpha 3 migrates ErdOS from Openbox/X11 to labwc/Wayland.
Alpha 2 remains available as the previous Openbox release; earlier source is in Git history.

- Keep Sakura, regular Firefox, PCManFM, Twig and the single-window GTK Settings app.
- Replace Skippy with labwc's native persistent thumbnail switcher. Preserve
  Super-only/Super+O, swipe-up invocation and Escape/swipe-down cancellation.
- Replace graphical workspace overview with a Workspaces menu; retain dynamic
  spare workspaces, existing selection shortcuts and shared multi-monitor spaces.
- Handle gestures, touchpad menu remapping and workspaces inside the compositor;
  remove the raw libinput/X11 gesture daemon and device access rule.
- Port Settings, custom commands, startup editing and menu editing to labwc.
- Replace XRandR, hsetroot and scrot with Wayland output control, swaybg and grim.
- Keep Debian power defaults, no panel/dock, square decorations and no shadows,
  blur or animations. Build dependencies stay outside the image.
- Retain XWayland for compatibility and small GTK/wlroots portal backends.
- Preserve the previous X11 development ISO alongside the new Wayland image for
  comparison. Build scripts perform no commits or publication.
