# Start the desktop only after a local login on tty1.
if [ -n "${BASH_VERSION:-}" ] && [ -f "$HOME/.bashrc" ]; then
    . "$HOME/.bashrc"
fi
if [ -z "${WAYLAND_DISPLAY:-}" ] && [ -z "${DISPLAY:-}" ] && [ "$(tty)" = /dev/tty1 ] && [ "$(id -u)" -ne 0 ]; then
    exec labwc
fi
