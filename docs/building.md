# Build and customize ErdOS

Use **Debian 13 amd64** with at least 20 GB free on a normal Linux filesystem.
Internet is required for signed Debian/Mozilla packages and installer components.
Root is used for live-build's chroot/mounts; the script does not write USB drives
or partition disks.

```sh
sudo apt update
sudo apt install live-build debootstrap xorriso squashfs-tools wget cpio file apt-utils
sudo apt install $(cat scripts/build-dependencies.txt)
sudo ./build.sh
```

## Build process

1. Stage `config/`, official bootloader links, pinned Twig and compositor notices.
2. Build pinned labwc 0.9.7 with statically linked wlroots 0.19.2. The build is
   stripped/size-optimized, uses GLES2 plus the built-in pixman fallback and
   excludes Vulkan, example programs, translation catalogs and build-time downloads.
3. Install the small Wayland runtime and existing default applications. XWayland
   provides compatibility; Xorg/Openbox/Skippy and old X11 helpers are absent.
4. Build BIOS/UEFI live media with Debian's offline text installer. Partitioning,
   disk selection and final write approval remain interactive. The installer
   configures signed online APT sources for later use.
5. Verify embedded configuration, installer policy, required package retention,
   Twig, the compositor binary/source hashes and the APT-cache budget before replacing
   `dist/erdos-amd64.iso` and its `.sha256` file.

Logs and temporary state are under `work/build-XXXXXXXX`. Never delete a build
while it is running or has active mounts. The successful ISO is independent of
this directory. Root-owned generated build state can be removed after validating
the image and confirming its mounts have gone away. The previous X11 development
ISO is intentionally retained as `dist/erdos-x11-dev.iso`.

`./build.sh --prepare` stages source without compiling or building an ISO.
`./scripts/build-helpers.sh` produces `release-tools/labwc` and its build record
for the optional existing-install updater. Compiler headers, Meson, Ninja, hwdata
and development libraries are host-only dependencies, not live-image packages.

## Configuration map

| Source | Purpose |
| --- | --- |
| `config/package-lists/desktop.list.chroot` | Runtime package selection |
| `config/includes.chroot/etc/skel/.profile` | Console login launches labwc |
| `config/includes.chroot/etc/skel/.config/labwc/` | Keys, menu, input, theme and session startup |
| `config/includes.chroot/usr/local/lib/erdos/` | Settings, defaults and display confirmation |
| `config/includes.chroot/etc/erdos/gestures.conf` | Default compositor swipe bindings |
| `vendor/labwc/src/erdos.c` | Native gesture, switcher, Super-key and hotplug integration |
| `vendor/labwc/src/cycle/` | Live overview, blurred backdrop, dock and regular window switcher |
| `vendor/labwc/src/workspaces.c` | Event-driven safe spare-workspace handling |
| `vendor/wlroots/` | Pinned compositor support library, statically linked |
| `config/includes.installer/` | Offline installation defaults and signed APT setup |

The pinned upstream revisions and ErdOS modifications are recorded in each
vendor directory's `UPSTREAM`. Runtime build provenance is installed at
`/usr/local/share/doc/labwc/build.json`. Include the complete source archive when
distributing a modified compositor. [Licenses and provenance](../THIRD_PARTY.md).

## Regular Firefox

The image installs Mozilla's **`firefox`** package, not Debian's
`firefox-esr`. It removes Chromium from the package list. New-account web
associations point to `firefox.desktop`; the menu and app shortcuts still honor
subsequent per-user browser selections. Alpha 1 used Chromium; Alpha 2 uses this regular Firefox package.

The minbase bootstrap includes the already-required `ca-certificates` package
before the first Mozilla HTTPS request. This changes installation order, not
the runtime package set.

The Mozilla APT repository is configured through live-build's documented
`config/archives/mozilla.{list,key,pref}.chroot` mechanism. The temporary build
source names its key explicitly. The runtime key is installed at
`/etc/apt/keyrings/packages.mozilla.org.asc`; `mozilla.sources` uses Signed-By
to restrict it to Mozilla. Both live-session setup and installer finish setup
write this source locally, so installation stays offline and later Firefox
updates use normal signed APT updates. Pinning applies only to `firefox` and
its language packs, not every package from that repository.

The checked-in ASCII public key was fetched from Mozilla's official repository
and verified against fingerprint
`35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3`. Its SHA-256 is
`3ecc63922b7795eb23fdc449ff9396f9114cb3cf186d6f5b53ad4cc3ebfbb11f`.
No runtime GPG tool, Snap or Flatpak is required. The desktop updater also
installs this scoped repository before installing regular Firefox, while
preserving existing per-user default associations.

[Mozilla's official DEB installation instructions](https://support.mozilla.org/en-US/kb/install-firefox-linux)
and [Debian Live additional-repository documentation](https://live-team.pages.debian.net/live-manual/html/live-manual/customizing-package-installation.en.html)
describe the package/repository and live-build mechanisms.


## Existing installations

The [hosted desktop updater](updates.md) preserves user configuration and
machine-specific fixes. Its current bundle targets the older Alpha 3 compositor;
it does not install the Alpha 5 compositor or migrate an X11 installation.
`scripts/update-desktop.sh` is a compatibility entry point for that same updater,
not a package installer or a way to install the latest checkout. Use the tested
ISO for a fresh installation of the current release.

Builds follow current signed package repositories and are not bit-for-bit
reproducible. A checksum detects corruption; it is not a signature or a hardware
compatibility guarantee. See [validation](testing.md) and [release preparation](releasing.md).
