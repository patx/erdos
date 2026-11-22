# Third-party software and assets

The root MIT license covers ErdOS’s original code and documentation. It does not
relicense the following upstream material or the packages placed in an ISO.

| Material | Upstream | Terms and notices |
| --- | --- | --- |
| `vendor/labwc/` | [labwc](https://github.com/labwc/labwc), version 0.9.7 | GPL-2.0-only; licenses and pinned revision retained; ErdOS native integration documented in `UPSTREAM` |
| `vendor/wlroots/` | [wlroots](https://gitlab.freedesktop.org/wlroots/wlroots), version 0.19.2 | MIT; statically linked to labwc, licenses and pinned revision retained |
| `vendor/twig/` runtime, desktop entry, icons and manual | [Twig](https://gitman.io/patx/twig), commit `a9123c2ecf1e89eaa31cbf178a434733bba6ead8` | MIT; retain `vendor/twig/LICENSE` and `UPSTREAM` |
| Templates and adaptations in `config/bootloaders/` | Debian live-build, source package `1:20250505+deb13u1` | GPL-3.0-or-later; see `LICENSES/live-build-copyright` and `LICENSES/GPL-3.0-or-later.txt` |
| Website app icons in `docs/assets/apps/` | Firefox artwork from Mozilla; Sakura/Adwaita icons from Debian and vendored Twig | See [icon credits](docs/assets/apps/credits.html), `LICENSES/firefox-artwork-notice`, `LICENSES/sakura-artwork-copyright`, `LICENSES/adwaita-icon-theme-copyright` and `vendor/twig/LICENSE`; unmodified artwork |
| Programs, libraries, fonts, firmware and bootloader binaries in a built ISO | Debian’s main and non-free-firmware archives; regular Firefox from Mozilla’s official APT repository | Each package’s own license; these are not covered by ErdOS’s MIT license |

Vendored runtime licenses and provenance are installed into their directories
under `/usr/local/share/doc/`. The labwc build record identifies its binary hash and complete source-tree
hashes for labwc and its statically linked wlroots library. ErdOS's native
integration is GPL-2.0-only as part of labwc. Both complete modified source trees
and their license notices are included in the source archive.

A release includes a package/version manifest for identifying the exact Debian
packages in that image. Debian source packages can be obtained from the matching
Debian archive with source repositories enabled. Retain the matching source and
notices when redistributing an image; the package manifest is an inventory, not
an archive of all corresponding source. See [release preparation](docs/releasing.md).

Debian and upstream project names identify the software on which ErdOS is based;
this project does not claim their endorsement.

Alpha 2 replaces Chromium with unmodified regular Firefox from
Mozilla, installed as its official signed DEB package. The Mozilla repository's
public signing key is included for package verification, with its fingerprint
recorded in [build instructions](docs/building.md#regular-firefox).
Mozilla/Firefox names and marks identify that upstream software. Earlier Chromium artwork remains in the Alpha 1 Git tag and source archive.
