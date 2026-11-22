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
