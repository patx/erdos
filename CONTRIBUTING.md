# Contributing to ErdOS

ErdOS aims for a small installed Debian/Openbox system with useful defaults.
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

The source CI runs these checks and compiles the native helpers and physics-free
overview; it does not claim to build or boot-test an ISO. For changes affecting
the installer or runtime,
follow [testing.md](docs/testing.md) and report the actual checks performed.
Avoid tests that only repeat configuration values; prefer the affected behavior
in a disposable VM.

## Website

`docs/` is a plain HTML/CSS/JavaScript site. It has no package manager, framework,
remote font or analytics dependency. Use relative asset paths so it works at
`https://patx.github.io/erdos/` and from a local server:

```sh
python3 -m http.server 8000 --directory docs
```

Check desktop and narrow mobile widths, keyboard navigation, links and downloads.
Release facts are in `docs/release.json`; do not invent a published release or
link to assets that have not been uploaded.

## License

Contribute original work under the project’s MIT license. Preserve the upstream
licenses of Twig and Debian-derived templates; see [THIRD_PARTY.md](THIRD_PARTY.md).
