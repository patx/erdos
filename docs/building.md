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

## Automatic cleanup and logs

`build.sh` owns a temporary directory under `work/` and removes it after success,
failure, Ctrl+C or SIGTERM. It stops its own child process group and unmounts
filesystems below that workspace before removal. It never deletes through a
remaining mount. A failed or interrupted build preserves the previous verified
ISO and checksum. Successful publication copies/checks the new image first,
replaces the canonical pair, then deletes older top-level `erdos*.iso` images,
their sidecars and standard stale release companions in `dist/`. Source and
other projects are outside this cleanup boundary.

Only the latest log for each build, staging check or test is kept under ignored
`logs/`. Each is capped at 8 MiB, retaining the tail if necessary. No full failed
build tree or compiler copy in `release-tools/` is retained by the ISO build.
`./build.sh --prepare` checks staging without compiling/building and cleans its
staged files on exit. `./scripts/build-helpers.sh OUTPUT_DIRECTORY` remains an
explicit way to retain a requested standalone compositor binary; its compiler
temporary directory is cleaned by its existing exit trap.

One managed build/staging/test runs at a time per checkout. Another invocation
fails clearly rather than deleting an active run's data. On the next run, marked
abandoned workspaces can be recovered after verifying their recorded owner is no
longer active. Docker recovery requires a Docker wrapper and checks the exact
per-run ownership label. Unknown active process groups, reused PIDs, unmount
failures or an unavailable Docker daemon produce an explicit cleanup error and
leave the workspace for inspection. SIGKILL/power loss cannot run exit handlers;
never manually remove a leftover mounted/active tree to bypass those checks.
Recovery also checks the boot and PID namespace before acting on recorded PIDs.
An interrupted publication that leaves `dist/.erdos-publish-*` blocks the next
run for inspection, preserving its backup rather than guessing which pair to keep.

## Disposable Docker builds

With Docker available, a non-Debian host can run:

```sh
./scripts/build-in-docker.sh
```

This uses an owned `debian:13` container with live-build's required privileged
mount access. The host project is mounted read-only. Only its disposable result
workspace is writable in the container. The entry point installs compiler/build
prerequisites into the temporary container, copies the allowlisted public source
to its native filesystem, builds/verifies there, and returns the ISO/checksum for
host publication. Container build trees, VM files and APT caches disappear when
the container is removed; the shared Debian base image stays cached. Future
builds reinstall build tools rather than retaining a multi-gigabyte container.
No unrelated containers, images, volumes or build caches are pruned.

## Managed tests

Use the wrapper instead of manually retaining test directories:

```sh
./scripts/run-test.sh python3 scripts/check-project.py
./scripts/run-test.sh python3 scripts/tests/test_workspaces.py
```

Test programs must place disposable VM disks, extracted systems and screenshots
under `$ERDOS_TEST_DIR` (also available as `$ERDOS_WORK_DIR`). On host tests,
`TMPDIR` points inside that workspace. Print small results to stdout/stderr so
they remain in `logs/latest-test.log`; save accepted benchmark results in the
tracked footprint report as part of the test procedure. Background children are
stopped before files are removed, even when the main test command exits early.
Keep test/VM processes in the foreground; do not daemonize or detach them into
new sessions outside the managed process group.

For a temporary Debian environment:

```sh
./scripts/run-in-debian.sh bash -c 'echo "Test workspace: $ERDOS_TEST_DIR"'
```

Install any required tools within that disposable container. `/project` exposes
the source/latest ISO read-only, and `/artifacts` is `$ERDOS_TEST_DIR`. Add
`--privileged` before the command only for KVM/mount tests that require it. The
container uses `--rm` and per-run cleanup, including on command failure; the host
wrapper also removes its own container after interruption. This is privileged
build tooling when requested, not a security sandbox for untrusted code.

## Upstream compositor maintenance

Our [Gitman maintenance fork](https://gitman.io/patx/labwc-erdos) retains the
original GitHub history and focused ErdOS commits. The build uses the exact
vendored snapshot pinned in [labwc-fork.json](../vendor/labwc-fork.json).
See [upstream-labwc.md](upstream-labwc.md) for fetch-only GitHub setup, source
checks, deliberate merges, safe imports and validation. Establishing the fork
did not upgrade labwc or wlroots or change the current runtime source.

## Configuration map

| Source | Purpose |
| --- | --- |
| `config/package-lists/desktop.list.chroot` | Runtime package selection |
| `config/includes.chroot/etc/skel/.profile` | Console login launches labwc |
| `config/includes.chroot/etc/skel/.config/labwc/` | Keys, menu, input, theme and session startup |
| `config/includes.chroot/usr/local/lib/erdos/` | Settings, defaults and display confirmation |
| `config/includes.chroot/etc/erdos/gestures.conf` | Default compositor swipe bindings |
| `vendor/labwc/src/erdos.c` | Native gesture, switcher, Super-key and hotplug integration |
| `vendor/labwc/src/menu/menu.c` | Desktop menu with on-open clock and battery status |
| `vendor/labwc/src/cycle/` | Live overview, blurred backdrop and regular window switcher |
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
