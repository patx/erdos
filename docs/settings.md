# ErdOS Settings

Open **Settings** from the desktop right-click menu, Applications, or **Super + I**.
Twelve sections share one GTK window. The app reuses Python 3, GTK 3, X11,
NetworkManager, BlueZ and PipeWire. Resolution controls use `xrandr` from Debian's
`x11-xserver-utils` package. There is no resident Settings daemon; the app exits
when closed. Display confirmation uses a short-lived rollback helper.

| Section | Controls |
| --- | --- |
| Appearance | GTK themes, font, dark preference, solid color and image backgrounds  |
| Default Programs | Select the terminal, web browser, file manager and text editor used by the menu and app shortcuts |
| Touchpad | Natural scrolling, tap to click, two-finger right-click, pointer speed |
| Keyboard | Dynamic/fixed workspaces, Super-only overview, Openbox shortcuts and custom application commands |
| Menu | Add, edit, delete and reorder right-click menu entries and separators |
| Gestures | Swipe distance and actions, including window/workspace overviews |
| Displays | Per-output resolution, timed confirmation, automatic extension, laptop brightness |
| Sound | Default output/input device, volume and mute using PipeWire |
| Network | Current Wi-Fi and internet state, radio on/off, scan/connect, saved Wi-Fi profiles and device disconnect |
| Bluetooth | Adapter power, scan, pair with confirmation/PIN, connect/disconnect, trust and forget |
| Power | Battery charge, charging status, external power, health and cycle count when available |
| Date & Time | Current system time, searchable time zones, preview, time-zone selection and automatic-sync status |

Use the Apply button for the setting being changed. Network and Bluetooth
operations have their own action buttons; Power displays information only.
Apply operations show a dismissible message at the bottom of the window. Errors
are distinguished from successful changes; sections that fail to load offer
**Retry**. A missing battery, Bluetooth adapter or audio device is reported in
its section rather than treated as a failed operation.
Service discovery and network operations run without freezing the interface.
Settings runs as your normal desktop user. NetworkManager and time-zone changes
use existing authorization policies; a graphical administrator-password prompt
may appear. Time-zone changes apply to every user and do not change the underlying
clock. Battery details depend on hardware; this version does not set charge limits
or suspend policy. Time and battery refresh only while Settings is open.

Wi-Fi passwords are passed to nmcli through standard input, never in the command
line or ErdOS preference files. NetworkManager manages saved secrets. Enterprise
Wi-Fi, VPNs and advanced IP settings remain available through Network Connections
in Applications. This app does not embed external editors.

## Background images

Choose an image or solid color in Appearance.

In **Appearance**, choose **Background → Image**, then **Choose image**. Choose a
layout and click **Apply appearance**:

- **Fill:** preserve proportions and crop to cover the screen.
- **Fit:** preserve the whole image, using Desktop color around it.
- **Center:** show the image at its original size, centered.
- **Tile:** repeat the image at its original size.

**Remove image** selects Solid color; apply to remove the saved wallpaper copy
and return to your chosen Desktop color. The original file is never deleted.
Choosing Solid color and applying has the same effect.

A private copy is saved as `~/.config/erdos/background-image` (or beneath
`XDG_CONFIG_HOME`). The original can then be moved or its USB drive removed.
Wallpaper selection and layout are saved in `settings.json`, restored at login,
and reapplied after display changes by the existing desktop listener. The same
image/layout is used across connected screens; separate wallpapers per monitor
are not configured here. Missing or unreadable saved images fall back to Desktop
color. Unreadable new files are rejected before changing the saved selection.

This reuses hsetroot and its Imlib2 decoder already included in ErdOS. No packages,
polling timer or wallpaper daemon are added. Installed space grows by the chosen
image plus a small amount of code; rendered images use X-server memory.

## Resolution changes

Choose advertised resolutions under Displays and click **Test resolution**.
**Keep resolution** saves the selection; **Revert**, a 15-second timeout, or the
Settings process exiting restores the previous layout. A short-lived helper owns
the timeout independently of the GUI. For ErdOS's normal horizontal layout,
outputs are repositioned side by side when their widths change. The primary
output is preserved. If a monitor disappears during confirmation, the automatic
layout helper restores a usable arrangement for the remaining screens.

Confirmed modes are restored at login when the same outputs are connected and
still advertise them. A monitor connection change reapplies automatic preferred
modes; use Settings again if needed. **Refresh displays** reloads available modes.
Custom modelines, rotation, scaling and mirroring are not configured here. Return
rotated outputs to normal before using this editor. Turning automatic extension
off retains the current layout and stops automatic rearrangement. Laptop brightness
uses brightnessctl; external-monitor DDC brightness is not included.

## Workspaces and shortcuts

Dynamic workspaces are enabled by default. ErdOS retains one spare after the last
occupied or current workspace, including minimized windows. Empty gaps keep their
numbers; only unused trailing workspaces disappear. Sticky windows do not create
extra workspaces. Switching to the spare creates another spare. The existing
session listener reacts to X11 events, with no polling loop or additional daemon.
All monitors share the same workspace set.

Disable dynamic mode in Keyboard to choose a fixed minimum count. A workspace
containing windows, or the current workspace, is retained even if the requested
count is lower. Settings changes take effect in the existing listener.

- **Super alone** (on release) or **Super + O**: all-window overview.
- **Super + Shift + O**: Skippy workspace overview.
- **Super + Space**, **Menu**, or desktop right-click: Openbox menu.
- **Shift + Super + 1–9** or **Super + F1–F9**: select an existing workspace.
- **Ctrl + Shift + Super + 1–9**: send a window to an existing workspace.

Super-only activation is cancelled by another key or mouse button, preserving
Super shortcuts. It can be disabled in Keyboard. Skippy uses a small documented
ErdOS patch for one-shot paging, so neither overview needs a persistent Skippy
daemon. Physics and animation remain disabled. Three-finger up still opens the
window overview; workspace overview is also available as a configurable gesture.

GTK themes/fonts affect newly opened applications; some existing windows need to
be reopened. Openbox decoration themes are separate. Touchpad changes apply to
connected libinput touchpads and at login; apply again after attaching another
touchpad. Sound device lists refresh on reopening Settings, and existing streams
may remain on their previous device after selecting a new default.

Preferences live under `~/.config/erdos/settings.json`,
`~/.config/erdos/gestures.conf`, `~/.config/gtk-3.0/settings.ini` and Openbox's existing
configuration. `XDG_CONFIG_HOME` is respected. Replacements are atomic with one
`.previous` backup. Live-session changes disappear at reboot without persistence.

## Bluetooth and automatic time

Bluetooth uses BlueZ directly through the existing GTK/Gio libraries. Turn on the
adapter, put your device in pairing mode, scan, then choose **Pair & connect**.
Confirm matching codes or enter the device's PIN when prompted. **Trust** permits
future connections without asking again; **Untrust** revokes that preference.
**Forget** asks before removing pairing information. Scanning stops after 30
seconds, when leaving the tab or closing Settings. Pairing prompts exist only
while Settings is open. There is no Bluetooth tray or separate settings daemon.
PipeWire Bluetooth audio support is included. Bluetooth file transfer is not
included.
Hardware/firmware must support the adapter; VMs usually need USB passthrough.

`systemd-timesyncd` starts by default in live and installed systems and synchronizes
when a time server becomes reachable. The installer remains fully offline.
Date & Time shows whether synchronization is enabled and complete, with buttons
to enable it and refresh status. It does not block boot waiting for the network.
Both live and installed sessions use the same signed HTTPS Debian repositories;
APT no longer uses the live media as an update source. If APT reports signatures
or metadata “not valid yet,” check synchronization and the system clock. Do not
disable signature or date checks. Time-zone selection alone does not fix a wrong
system clock; networks that block NTP may require correcting it manually.

## Current power behavior

Power currently reports battery information; it does not change sleep policy.
ErdOS uses Debian's systemd-logind defaults: idle does not suspend the computer;
closing the lid normally suspends, while docking or connecting another display
normally leaves it awake. A brief power-button press requests shutdown and a
sleep key requests suspend. Hardware support and inhibitors can affect these
actions. The X server's default display blanking/DPMS timeout is 10 minutes in
the tested VM; display power saving is separate from computer sleep. There is no
screen locker in this image, including on resume. See Debian's
[logind documentation](https://manpages.debian.org/trixie/systemd/logind.conf.5.en.html).

## Custom keyboard shortcuts

In Keyboard, use **Add shortcut**, then double-click the Shortcut and Command
fields. For example, `W-p` can launch `pcmanfm`. Use **Apply shortcuts** to save;
**Remove selected** removes a custom entry when you apply. Conflicts with existing
shortcuts are rejected. Commands run as your user only when invoked, not while
saving. Changes are stored in your Openbox configuration with a `.previous`
backup; no additional service or package is needed.

## Workspace swipe direction

The default four-finger swipe left selects the next workspace (to the right);
swipe right selects the previous workspace (to the left). Existing saved gesture
overrides are preserved. Change these in Settings → Gestures and apply to update
an existing installation.

## Right-click menu

Open **Menu** in Settings to edit the root Openbox menu. Double-click a name or
command; use **Add item**, **Add separator**, **Delete**, **Move up** and **Move
down**, then **Apply menu**. New items launch a command as your desktop user.
Applications remains an automatically generated submenu; its contents continue
to follow installed apps. Existing nested menus and built-in actions such as
Logout are preserved when renamed or moved. Their internals are not edited here.

Changes apply immediately and persist in `~/.config/openbox/menu.xml`, with the
previous version saved as `menu.xml.previous`. If another program changes that
file while Settings is open, reopen Settings before applying. **Super + I**
still opens Settings after deleting its menu entry.

## Default appearance

New users get Adwaita dark applications and the small ErdOS Openbox theme, with
matching dark menus, window borders and workspace indicators. All use the
existing DejaVu Sans font and Adwaita icons. Appearance can still change GTK
themes, fonts and the dark preference; this does not replace a user's Openbox
theme selection. No theme engine, compositor or resident settings service is added.

[View the installed Alpha 2 Settings window](settings-alpha2.png).

## Default programs

**Settings → Default Programs** selects the terminal, web browser, file manager
and text editor. Install alternatives first, click **Refresh application list**,
choose the programs, then **Apply default programs**. No logout is needed.

The top-level right-click items are **Terminal**, **Web Browser**, **File Manager**
and **Text Editor**. They share the same launcher as Super+Enter/Ctrl+Alt+T,
Super+B, Super+E and Super+T. The Applications submenu keeps actual app names.

Browser selection updates HTTP, HTTPS and HTML associations. The launcher reads
the current HTTPS/HTTP association on each use, so changes made by a browser or
another association editor are honored. File Manager uses `inode/directory`;
Text Editor uses `text/plain`. Other file types retain their own associations.

Terminal choice is stored per user in `~/.config/erdos/settings.json`, beneath
`XDG_CONFIG_HOME` when set. **System terminal** uses Debian's existing
`x-terminal-emulator` alternative. If a selected terminal is removed, ErdOS
falls back to that system terminal. This choice controls the ErdOS menu/shortcuts,
not how third-party desktop entries with `Terminal=true` choose their terminal.

New accounts start with Sakura (system terminal), regular
Firefox from Mozilla, PCManFM and Twig. Firefox ESR is not selected.
Existing user associations are preserved by the desktop updater. The helper
reuses Python/GIO; no package, polling loop or settings daemon is added.

These defaults are included in Alpha 2.

## Network feedback

The Network tab shows the current Wi-Fi state in plain language: connected to a
connection, connecting, not connected, radio off, unavailable, or no adapter.
Internet availability is separate: a connected access point can still have no
internet access or need browser sign-in. Active wired connections are shown
separately. Raw device tables, connection UUIDs and D-Bus paths are not used as
success messages.

**Turn Wi-Fi on/off** acts immediately. **Scan for networks** refreshes the list;
**Connect to selected network** shows progress, clears the password field and
reports the refreshed connection state. Failed actions refresh that state too
and remain errors rather than generic confirmations. A selected connected
network cannot be connected again. Saved choices list Wi-Fi profiles only.
**Disconnect Wi-Fi** disconnects active wireless devices and prevents immediate
automatic reactivation until a manual connection/reboot, instead of merely
deactivating a saved profile. Wired connections remain separate.

While this tab is visible, NetworkManager D-Bus events trigger a short debounced
refresh. Old connection confirmations disappear when the connection state changes.
There is no periodic network polling or extra daemon; the listener is removed
when Settings closes. **Refresh status** is available as a manual fallback.
