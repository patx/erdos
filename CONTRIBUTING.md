# Contributing to ErdOS

ErdOS aims for a small installed Debian/labwc system with useful defaults.
Prefer existing libraries, event-driven helpers, and Debian packages. Explain
any extra installed dependencies and their size before adding a service or UI.

## Before opening a change

Search existing issues and describe the user-visible problem. For bugs, include
ISO checksum, live or installed session, BIOS/UEFI mode, hardware/VM model, and
steps to reproduce. Remove passwords, Wi-Fi credentials and identifying data
from logs. Private VM fixtures and full build logs do not belong in the source
repository.

Keep changes focused. Installer changes must preserve interactive disk selection,
partitioning, and erase/write approval. Never put a target disk, account password,
or automatic erase confirmation into the production preseed.

## Build/test storage

Use the managed wrappers and disposable workspaces described in
[building.md](docs/building.md#automatic-cleanup-and-logs) and [AGENTS.md](AGENTS.md).
Do not retain ad hoc VM disks, chroot copies or persistent build containers.
Only the latest verified ISO is kept after an ordinary build.

## Local checks

```sh
python3 scripts/check-project.py
```

On Debian 13 amd64, also install the compiler prerequisites from
[building.md](docs/building.md) and run:

```sh
./scripts/build-helpers.sh
./build.sh --prepare
```

The source CI runs these checks and compiles the pinned compositor and native live
overview; it does not claim to build or boot-test an ISO. For changes affecting
the installer or runtime,
follow [testing.md](docs/testing.md) and report the actual checks performed.
Avoid tests that only repeat configuration values; prefer the affected behavior
in a disposable VM.

## Compositor changes

Develop compositor changes in the [labwc maintenance fork](https://gitman.io/patx/labwc-erdos)
and import a reviewed commit, rather than letting the vendored copy diverge.
The [upstream maintenance guide](docs/upstream-labwc.md) documents focused commits,
GitHub fetching, source pins, imports and upgrade validation. Ordinary builds
remain offline with respect to compositor sources and need no submodule clone.

## Website

`docs/` is a plain HTML/CSS site. It has no package manager, framework,
remote font or analytics dependency. Use relative asset paths so it works at
`https://patx.gitman.io/erdos/` and from a local server:

```sh
python3 -m http.server 8000 --directory docs
```

Check desktop and narrow mobile widths, keyboard navigation, links and downloads.
Release facts are in `docs/release.json`; do not invent a published release or
link to assets that have not been uploaded.

## License

Contribute original work under the project’s MIT license. Preserve the upstream
licenses of Twig and Debian-derived templates; see [THIRD_PARTY.md](THIRD_PARTY.md).
