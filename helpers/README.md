# Desktop implementation

The compositor is built from pinned sources in `vendor/labwc` and
`vendor/wlroots`. `scripts/build-helpers.sh` builds it with a static wlroots
library, GLES2/pixman rendering and no animated effects. Runtime actions,
gestures and dynamic workspaces live in `vendor/labwc/src/erdos.c` and its
small integration call sites. Old X11 helpers and Skippy are removed.
