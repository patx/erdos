# ErdOS Settings

Open **Settings** from the desktop menu or **Super + I**. Alpha 3
uses labwc on Wayland. Thirteen sections share one Python/GTK window; no
Settings daemon remains when you close it. Apply results distinguish errors from
success and can be dismissed.

| Section | Controls |
| --- | --- |
| Appearance | GTK theme, font, dark preference, desktop color and image backgrounds |
| Default Programs | Terminal, browser, file manager and text editor |
| Touchpad | Natural scrolling, tapping, clickfinger right-click and pointer speed |
| Keyboard | Dynamic/fixed workspaces, Super-only thumbnails, shortcuts and custom commands |
| Menu | Edit/reorder menu entries; enable three-finger and Super + right-click triggers |
| Startup Applications | Edit labwc login commands with syntax validation and backup |
| Gestures | Swipe distance and configurable three/four-finger actions |
| Displays | Resolutions with timed rollback, automatic extension and laptop brightness |
| Sound | PipeWire input/output devices, volume and mute |
| Network | Wi-Fi/internet state, radio, scan/connect and saved profiles |
| Bluetooth | Scan, pair, connect/disconnect, trust and forget |
| Power | Battery status, capacity, health and cycles where available |
| Date & Time | Current time, time zone and synchronization status |

## Default programs

The menu's Terminal, Web Browser, File Manager and Text Editor entries and their
keyboard shortcuts use your selected defaults. Initial apps are Sakura, Firefox,
PCManFM and Twig. Install alternatives, refresh the app list and apply a selection.
Browser, directory and text choices use desktop MIME associations; terminal
selection is per user, with the system terminal as fallback. Other file types
keep their associations. Existing open apps are unaffected.

## Backgrounds and appearance

Select a supported image and Fill, Fit, Center or Tile. ErdOS validates and copies
it into `~/.config/erdos/background-image`, so moving the original does not break
login. Remove image and Apply returns to the selected solid color and removes
only the private copy. Swaybg renders the background as a single process managed
by `erdos-background.service` in the user's systemd session. The Python launcher
executes swaybg rather than remaining resident. Backgrounds follow output changes.
GTK changes may require reopening an already running application. Windows and
menus use the supplied dark labwc theme, square corners and no shadows.

## Keyboard and workspaces

The native thumbnail switcher replaces Skippy. Super alone (on release), Super + O
or three fingers up opens it across workspaces and outputs. It remains open after
key/finger release. Click a thumbnail, or use arrows and Enter to select; Escape
or three fingers down cancels without sending Escape to an ordinary application.
Super + Tab / Super + Shift + Tab remains the ordinary current-workspace cycle.

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

Double-click a shortcut to edit it. W = Super, C = Ctrl, A = Alt, S = Shift.
Space-separated alternatives are supported. Custom commands run as your normal
user when invoked. Duplicate shortcuts and empty commands are rejected. Use key
names such as `Return`, `1` or `F1`, not old X11 hexadecimal keycodes. Fn/media-key
mode remains a keyboard/firmware setting.

## Menu

Edit `~/.config/labwc/menu.xml` through this section. Add/delete/reorder entries
and separators, or double-click a name/command. Apply saves a `.previous` backup.
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

## Gestures

A deliberate swipe triggers once when its distance and direction thresholds are
met, without waiting for finger release. Lower distance responds sooner but can
trigger accidentally. The compositor handles gestures directly; there is no raw
input listener, input-group membership, extra device ACL or gesture daemon.

| Gesture | Default |
| --- | --- |
| Three fingers up / down | Open / close thumbnail switcher |
| Three fingers left / right | Previous / next window on current workspace |
| Four fingers left / right | Next workspace (right) / previous workspace (left) |
| Four fingers up / down | Disabled; configurable, including Workspaces menu |

Change actions in Gestures and Apply. Three-finger tap/click is configured in
Menu rather than the swipe list. Gestures are ignored while the compositor is
locked. Physical support depends on the touchpad; typical VMs expose only a mouse.

## Displays

Resolutions come from the Wayland output-management protocol through `wlr-randr`.
A test must be confirmed within 15 seconds; timeout, Revert, closing Settings or
a helper error restores the previous layout where possible. Confirmed choices
are saved for the same connected outputs.

Automatic layout keeps the built-in laptop screen at the left and extends
external monitors to its right. Workspaces span all screens. Hotplug invokes a
one-shot layout helper, not a resident monitor polling process. Disabling the
policy leaves the current layout untouched. Custom rotated layouts should be
returned to normal orientation before editing resolutions here. Hardware
backlight controls do not imply DDC brightness support for external monitors.

## Network, Bluetooth and sound

NetworkManager provides current connection state and saved profiles. Wi-Fi
connection and internet reachability are shown separately. Network changes update
the visible controls via D-Bus events. Advanced profiles remain available through
Advanced Network Configuration. Bluetooth uses BlueZ and its existing authorization agent;
Sound uses PipeWire/WirePlumber. Missing adapters/devices are reported rather than
shown as connected. These sections do not install device-specific drivers.

## Power and time

Power is informational. Debian's logind defaults handle lid closure, sleep keys
and power-button presses; no charge-limit or automatic-sleep service is added.
There is no bundled screen locker, including on resume. Behavior depends on
hardware, docking and inhibitors. Closing the lid normally suspends except when
docked/using another display. See [Debian logind documentation](https://manpages.debian.org/trixie/systemd/logind.conf.5.en.html).

Date & Time shows the clock, a time-zone search/preview and synchronization
status. System-wide time changes use existing system authorization. Automatic
synchronization is enabled by default but requires connectivity. If APT reports
metadata/signatures are not valid yet, check the clock; signature validation is
never disabled to hide clock errors.

## Persistence and compatibility

User configuration lives in `~/.config/labwc` and `~/.config/erdos`. Changes persist
on installed systems; an ordinary nonpersistent live USB loses them at reboot.
GTK apps run natively on Wayland; XWayland supports older X11 applications. GTK
and wlroots portal backends provide file dialogs and screen-sharing integration.
No Qt desktop, panel or dock is installed.
