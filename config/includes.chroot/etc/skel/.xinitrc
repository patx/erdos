#!/bin/sh
export XDG_CURRENT_DESKTOP=Openbox
export XDG_SESSION_DESKTOP=openbox
export XDG_SESSION_TYPE=x11
# Make DISPLAY and XAUTHORITY available to activated user services.
if [ -d /etc/X11/xinit/xinitrc.d ]; then
    for script in /etc/X11/xinit/xinitrc.d/?*.sh; do
        [ ! -x "$script" ] || . "$script"
    done
fi
dbus-update-activation-environment --systemd DISPLAY XAUTHORITY XDG_CURRENT_DESKTOP XDG_SESSION_DESKTOP XDG_SESSION_TYPE
# Explicit startup avoids also launching distribution XDG autostart entries.
exec openbox --startup "$HOME/.config/openbox/autostart"
