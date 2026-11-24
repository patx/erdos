# Development

- Remove the overview dock, its renderer/status timer, launch helper and Settings
  tab. Keep the native live window overview and give its grid the freed space.
- Add a clickable 12-hour clock and battery percentage below Settings in the
  desktop menu, before Logout/Reboot/Power off. They open Date & Time and Power
  in the existing Settings window. Hide battery status when no system battery
  is available; refresh only when the menu opens. No new dependencies or daemon.
- Published Alpha 5 ISO, benchmarks and hosted updater remain unchanged.

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
