# Third-party software and assets

The root MIT license covers ErdOS’s original code and documentation. It does not
relicense the following upstream material or the packages placed in an ISO.

| Material | Upstream | Terms and notices |
| --- | --- | --- |
| `vendor/twig/` runtime, desktop entry, icons and manual | [Twig](https://gitman.io/patx/twig), commit `a9123c2ecf1e89eaa31cbf178a434733bba6ead8` | MIT; retain `vendor/twig/LICENSE` and `UPSTREAM` |
| Templates and adaptations in `config/bootloaders/` | Debian live-build, source package `1:20250505+deb13u1` | GPL-3.0-or-later; see `LICENSES/live-build-copyright` and `LICENSES/GPL-3.0-or-later.txt` |
| `vendor/skippy-xd/` | [Skippy-XD](https://github.com/felixfung/skippy-xd), commit `25402b43920965f4bfacadceb5b7dacbf5f6b026` | GPL-2.0-or-later; original source headers, `COPYING` and `UPSTREAM` retained; physics disabled; local one-shot paging patch documented in `UPSTREAM` |
| Website app icons in `docs/assets/apps/` | Icons from Debian Chromium/Sakura/Adwaita packages and vendored Twig | See [icon credits](docs/assets/apps/credits.html), `LICENSES/chromium-copyright`, `LICENSES/sakura-artwork-copyright`, `LICENSES/adwaita-icon-theme-copyright` and `vendor/twig/LICENSE`; unmodified artwork |
| Programs, libraries, fonts, firmware and bootloader binaries in a built ISO | Debian’s main and non-free-firmware archives | Each package’s own license; these are not covered by ErdOS’s MIT license |

Vendored runtime licenses and provenance are installed into their directories
under `/usr/local/share/doc/`. Skippy-XD’s build record also identifies its exact
upstream revision, modified Skippy source SHA256, disabled-physics build option
and binary SHA256.
Debian package copyright notices remain under `/usr/share/doc/` in the image,
including when other package documentation is trimmed. The original ErdOS logo
is in `branding/`; website assets use that same supplied logo and screenshots
of ErdOS, rather than stock images or externally hosted fonts.

A release includes a package/version manifest for identifying the exact Debian
packages in that image. Debian source packages can be obtained from the matching
Debian archive with source repositories enabled. Retain the matching source and
notices when redistributing an image; the package manifest is an inventory, not
an archive of all corresponding source. See [release preparation](docs/releasing.md).

Debian and upstream project names identify the software on which ErdOS is based;
this project does not claim their endorsement.
