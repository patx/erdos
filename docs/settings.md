# ErdOS Settings

Open **Settings** from the desktop menu or **Super + I**. The current checkout
has sixteen sections in one Python/GTK window. Native theme colors, grouped
controls, readable labels, keyboard focus, inline validation and Apply/Revert
feedback are shared across the app. No extra UI libraries, packages or background
services are added.

Beta 2 retains the dock-free overview and on-demand PCManFM. Clock and battery
status are in the desktop menu. The new Software and About sections, input and
display controls reuse installed dependencies. Signed component updates use APT;
no updater daemon, locker or idle listener is added.

## Editing and feedback

Related controls have an **Apply** (or **Save**) and **Revert** row. Apply becomes
available when something changes; Revert discards those unsaved edits. Switching
sections keeps your edits. Closing asks before discarding unsaved changes.
Settings stays open on errors so you can correct the value and try again.

While a change runs, its section is temporarily disabled; you can still browse
other sections. Saving another group waits until the current operation finishes.
If you close during an operation, it finishes before the application exits.
Refresh and loading messages are separate from save confirmations. Longer help
is available under **More information**.

A display trial has separate **Revert** and **Keep changes** buttons.
Closing during a trial requests rollback before closing. Error messages distinguish
a rejected mode from a successful restore, and the display list refreshes afterward.

| Section | Controls |
| --- | --- |
| Appearance | GTK 3, icon, and labwc themes, font, dark preference, accents, cursor theme/size, window-button position and optional minimize/maximize controls, desktop color and image backgrounds |
| Default Programs | Terminal, browser, file manager and text editor |
| Touchpad | Natural scrolling, tapping, clickfinger right-click, pointer speed, disable while typing/on external mouse |
| Mouse | Pointer and scroll speed, acceleration, natural scrolling and left-handed buttons |
| Keyboard | Layouts, repeat rate/delay, Caps Lock mapping, dynamic/fixed workspaces, Super-key overview, shortcuts and custom commands |
| Menu | Edit/reorder menu entries; enable three-finger and Super + right-click triggers |
| Startup Applications | Edit labwc login commands with syntax validation and backup |
| Gestures | Swipe distance and configurable three/four-finger actions |
| Displays | Enable/disable outputs, resolution, refresh rate, scale, rotation and position with timed rollback, automatic extension and laptop brightness |
| Sound | PipeWire input/output devices, volume and mute |
| Network | Wi-Fi/internet state, saved profiles, PEAP enterprise Wi-Fi, IPv4 and DNS |
| Bluetooth | Scan, pair, connect/disconnect, trust and forget |
| Power | Battery status, capacity, health and cycles, plus suspend and hibernate where available |
| Date & Time | Current time, time zone and synchronization status |
| Software | Interactive APT update, upgrade, unused-package purge and cache cleaning |
| About | Software version, hardware summary and Copy system information |

## Default programs

The menu's Terminal, Web Browser, File Manager and Text Editor entries and their
keyboard shortcuts use your selected defaults. Initial apps are Sakura, Firefox,
PCManFM and Twig. Install alternatives, refresh the app list and apply a selection.
Browser, directory and text choices use desktop MIME associations; terminal
selection is per user, with the system terminal as fallback. Other file types
keep their associations. Existing open apps are unaffected.

## Backgrounds and appearance

New profiles show only the close button on the left. Appearance → Window
controls offers Left/Right positioning and optional minimize/maximize buttons
for labwc and GTK apps that follow desktop decoration settings. Keyboard window
actions still work when their title-bar buttons are hidden. Existing user layouts are preserved until explicitly changed.
The regular Super+Tab switcher uses labwc’s unmodified 300×250 thumbnail defaults;
the overview uses its independent grid.

ErdOS starts with the bundled blue starfield wallpaper. Choose Image in
Settings to return to the bundled wallpaper after using a solid color.
Select a custom image and Fill, Fit, Center or Tile. ErdOS validates and copies
it into `~/.config/erdos/background-image`, so moving the original does not break
login. Remove image and Apply returns to the selected solid color and removes
only the private copy. Swaybg renders the background as a single process managed
by `erdos-background.service` in the user's systemd session. The Python launcher
executes swaybg rather than remaining resident. Backgrounds follow output changes.
**Prefer dark appearance** updates both GTK and the standard desktop portal
color-scheme preference. Firefox and supporting websites follow it when Firefox
uses its system theme/automatic website appearance. A browser theme or a site’s
own saved theme can override this preference; ErdOS does not forcibly recolor
websites. See [Firefox website appearance](https://support.mozilla.org/en-US/kb/change-website-appearance-settings-firefox)
for its browser-level options. Other GTK changes may require reopening an already running application. Windows and
menus use the supplied dark ErdOS theme by default.

**Application theme (GTK 3)** and **Application icon theme** set the widget
style and icons used by GTK 3 apps. The pickers show compatible themes already
installed on the system or for your user. **Window manager theme (labwc)** sets
the theme for window decorations and the desktop menu. Apply that choice to
reload labwc. An active custom desktop accent still sets the menu highlight.

**Desktop accent** sets the highlight in the labwc desktop menu.
**Application accent** sets selection and control highlights in GTK 3 apps
such as PCManFM. Use **Use the desktop accent for GTK 3 apps** to share one
color. Turn off a custom accent to return to the theme default. Reopen GTK 3
apps after applying the change.

**Cursor theme and size** use cursor themes already installed in the standard
XCursor paths. The compositor and GTK 3 settings are saved together, preserving
other appearance settings. Reopen apps that keep a previously loaded cursor.

For further customization, [labwc-tweaks](https://github.com/labwc/labwc-tweaks)
is the upstream graphical tool for labwc themes and compositor settings.
[nwg-look](https://github.com/nwg-piotr/nwg-look) provides additional GTK 3
appearance controls, including icon and cursor themes. Both are optional tools.

## Keyboard and workspaces

Set up to four XKB layouts in **Keyboard** and choose a shortcut to switch
between them. Enter comma-separated layout codes such as `us,gb`. Variant
codes follow the same order. Leave an entry blank to use that layout's default.
**Mouse** controls non-touch pointing devices independently of **Touchpad**.
Set key repeat speed (0 disables repeat), delay and Caps Lock behavior separately
from layouts. Caps Lock can remain normal, swap with Esc, act as Ctrl/Esc or be
disabled. Other XKB options and shortcuts are preserved; custom mappings can be
left unchanged. Touchpad can disable input while typing or while an external
mouse is present, where supported by libinput. Neither needs a listener daemon.

Tap Super or swipe three fingers up to open the live window overview on the
display nearest the pointer. It shows windows across workspaces and outputs.
Click a preview or use the arrow keys and Enter to select a window. A white glow
marks the arrow-key selection. Tap Super again or swipe three fingers down to
close the overview. Super + Tab / Super + Shift + Tab cycles current-workspace
windows in the regular switcher.

The opening desktop frame is blurred once. Window previews update while the
overview is open. There are no launchers or status widgets in the overview.
Use the desktop menu for applications, the clock and battery information.

Dynamic workspaces retain one empty workspace after the last occupied or current
workspace, including minimized windows. Empty gaps keep their numbers; only
unused trailing workspaces disappear. Sticky windows do not create extra spaces.
All monitors share the same workspace set. Disable dynamic mode to set a fixed
minimum; occupied/current workspaces are never removed to satisfy a smaller count.
This is event-driven inside the compositor, without a polling helper.

Super + Shift + O opens the **Workspaces** menu, also present in the root menu.
It lists workspaces and their windows. A separate graphical workspace overview is
not included. Four-finger up/down are disabled by default and remain configurable.

Window snapping uses labwc's native actions. Super + Left/Right snaps to halves;
Super + Up maximizes, and Super + Down unmaximizes/unsnaps to natural geometry.
Numpad snapping shortcuts remain available. Restore is validated across repeated
snapping/maximizing and output changes before a release is considered tested.

Select a shortcut and choose **Edit**, or double-click it. Shortcuts display as
`Super + B`; enter alternatives separated by a comma or slash, such as
`Super + Enter, Ctrl + Alt + T`. Existing labwc syntax (`W-Return C-A-t`) is also
accepted. Case differences, keysym aliases and repeated modifiers cannot bypass
duplicate checking. Custom commands run as your normal
user when invoked. Duplicate shortcuts and empty commands are rejected. Use key
names such as `Return`, `1` or `F1`, not old X11 hexadecimal keycodes. Fn/media-key
mode remains a keyboard/firmware setting.

## Menu

The default menu places a **12-hour clock** and **Battery: …%** after the app and
Settings entries, before Logout, Reboot and Power off. Clicking the clock opens
**Date & Time**; clicking the battery opens **Power**. An already-open Settings
window is reused. The clock uses local time, and the battery label includes
**Charging** when appropriate. Machines without a readable system battery omit
that row; mouse/keyboard peripheral batteries are excluded.

Values refresh each time the menu opens and remain unchanged while it stays
open. No polling timer, subprocess or service is added. These are built-in rows
in the menu editor: they can be reordered or removed while their dynamic labels
and actions are preserved. The default XML marks them with
`erdos-status="clock"` and `erdos-status="battery"`; their commands are
`erdos-settings --time` and `erdos-settings --power`. Existing custom menu files
are not overwritten. Add the marked items from the default
[`menu.xml`](../config/includes.chroot/etc/skel/.config/labwc/menu.xml) if migrating
an existing configuration. Old `~/.config/erdos/dock.ini` files are ignored.

Edit `~/.config/labwc/menu.xml` through this section. Add/delete/reorder entries
and separators. Select an item and choose **Edit**, or double-click its name/command.
Apply saves a `.previous` backup; Revert restores the editor’s last saved values.
Built-in actions and nested menus are preserved. Applications reads installed
desktop entries on demand; new graphical apps appear automatically. CLI-only
programs require a desktop entry to appear there. Super + I remains available if
you remove the Settings menu entry.

**Three-finger tap/click opens menu** replaces touchpad middle-click when enabled.
Tapping needs tap-to-click; a physical three-finger click needs clickfinger
support. Disable it to restore middle-click. Mouse middle-click is preserved.
**Super + right-click opens menu anywhere** is independently configurable.
Desktop right-click, Super + Space and the Menu key remain available. Apply menu
triggers changes them immediately; newly connected touchpads inherit the settings.

## Startup Applications

Edit `~/.config/labwc/autostart` directly. Keep the ErdOS session setup commands.
Add one application per line with `&` so it does not block later commands.
Save checks shell syntax without executing commands and keeps
`autostart.previous`. Changes run at the next login. Reload asks before discarding
unsaved changes; conflicting external edits require a reload before saving.

The default startup file no longer runs `pcmanfm --daemon-mode &`. Launch the
file manager through the menu or Super + E when needed. USB mounting and SMB/SFTP
support remain installed; automatic mounting runs while PCManFM is open. Existing
custom startup files are preserved. To adopt this behavior on an older profile,
remove its `pcmanfm --daemon-mode &` line here and log out and back in.

## Gestures

A deliberate swipe triggers once when its distance and direction thresholds are
met, without waiting for finger release. Lower distance responds sooner but can
trigger accidentally. The compositor handles gestures directly; there is no raw
input listener, input-group membership, extra device ACL or gesture daemon.

| Gesture | Default |
| --- | --- |
| Three fingers up / down | Open / close the live window overview |
| Three fingers left / right | Previous / next window on current workspace |
| Four fingers left / right | Next workspace (right) / previous workspace (left) |
| Four fingers up / down | Disabled; configurable, including Workspaces menu |

Change actions in Gestures and Apply. Three-finger tap/click is configured in
Menu rather than the swipe list. Gestures are ignored while the compositor is
locked. Physical support depends on the touchpad; typical VMs expose only a mouse.

## Displays

Resolutions come from the Wayland output-management protocol through `wlr-randr`.
Enable or disable connected outputs; at least one must remain enabled.
Disabled outputs can be turned back on and their state is saved for that display
combination. Every change uses the same confirmation/rollback flow.
Set a higher scale to make text and windows larger while keeping the display
at its native resolution. Set the refresh rate, rotation, and position for
each active output. Positions use logical pixels and stay where you set them
when you edit scale. Confirm changes within 15 seconds. Timeout, Revert,
closing Settings, or a helper error restores the previous settings where
possible. Confirmed settings are reused for the same connected outputs even
when automatic extension is disabled.

Automatic layout keeps the built-in laptop screen at the left and extends
external monitors to its right. Workspaces span all screens. Hotplug invokes a
one-shot layout helper. When automatic extension is disabled, connecting a
different combination of displays leaves the current layout in place.
Hardware backlight controls apply to the built-in panel.

## Network, Bluetooth and sound

NetworkManager provides current connection state and saved profiles. Wi-Fi
connection and internet reachability are shown separately. Network changes update
the visible controls via D-Bus events. Edit DHCP, a static IPv4 address,
the gateway, and IPv4 DNS on saved Wi-Fi and Ethernet profiles. Reconnect
to apply profile changes. Enterprise Wi-Fi supports PEAP with MSCHAPv2 and
requires a CA certificate and server domain. Enter the password again when
reconnecting to that profile. Other enterprise methods use `nmcli`.
Volume controls and media keys use
WirePlumber directly, so pulsemixer is not needed. Bluetooth uses BlueZ and its existing authorization agent;
Sound uses PipeWire/WirePlumber. Choosing an audio device loads its own volume
and mute state before Apply is available. **Refresh devices** picks up newly
connected devices without reopening Settings; apply or revert outstanding audio
edits first. Missing adapters/devices are reported rather than
shown as connected. These sections do not install device-specific drivers.

## Power and time

Power offers **Suspend now** and **Hibernate now** where logind reports them
available. Debian's logind policy handles lid closure, sleep keys and
power-button presses.
There is no bundled screen locker, including on resume. Behavior depends on
hardware, docking and inhibitors. Closing the lid normally suspends except when
docked/using another display. See [Debian logind documentation](https://manpages.debian.org/trixie/systemd/logind.conf.5.en.html).

Date & Time shows the clock, a time-zone search/preview and synchronization
status. System-wide time changes use existing system authorization. Automatic
synchronization is enabled by default but requires connectivity. If APT reports
metadata/signatures are not valid yet, check the clock; signature validation is
never disabled to hide clock errors.

## Software and About

Software opens the system terminal with one explicit command:

- Refresh package lists: `sudo apt-get update`.
- Upgrade packages: `sudo apt-get upgrade` (refresh lists first).
- Remove unused packages: `sudo apt-get autoremove --purge`, equivalent to APT's
  autopurge action. Review its package list before approving removals.
- Clear package cache: `sudo apt-get clean`. This removes downloaded package
  archives, not installed apps or repository indexes.

APT keeps its confirmation prompts; no unattended `-y` is used. The terminal
stays open after success, cancellation or failure so the result can be read.
No passwords are stored. These commands use configured signed repositories and
also update ErdOS components on package-managed installations. Log out after
desktop/compositor updates. They do not run automatically; see
[signed updates](updates.md) for legacy adoption.

About separates base-image identity from installed desktop package/source
versions, labwc/wlroots and Twig provenance. A running compositor digest that
differs from the installed one prompts logout/login. It also loads kernel,
architecture, CPU, model, RAM and root
filesystem usage on demand. **Copy system information** copies the displayed
report for troubleshooting. Hostnames, usernames, serials and network addresses
are omitted. Root filesystem usage is not the benchmark's installed-disk metric.

## Persistence and compatibility

User configuration lives in `~/.config/labwc` and `~/.config/erdos`. Changes persist
on installed systems; an ordinary nonpersistent live USB loses them at reboot.
GTK apps run natively on Wayland; XWayland supports older X11 applications. GTK
and wlroots portal backends provide file dialogs and screen-sharing integration.
No Qt desktop, panel or dock is installed.
