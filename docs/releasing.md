# Prepare a GitHub release and Pages site

Repository: <https://github.com/patx/erdos>. Website:
<https://patx.gitman.io/erdos/>. These instructions prepare artifacts locally;
none of the project scripts commit, tag, push, upload or publish anything.

## Source repository

Commit source, documentation, licenses, branding and the pinned third-party sources.
Keep `work/`, `dist/`, `downloads/`, `validation/`, `release-tools/`, disk images,
logs and local credentials out of Git. Inspect `git status --short` and
`git status --ignored --short` before staging. Do not add ignored artifacts with
`git add -f`. The generated source ZIP uses an allowlist and excludes local test
fixtures and generated binaries.

The existing local directory may already have Git initialized. An initial commit
and remote publication are separate maintainer actions; inspect the work before
performing either. The intended default branch is `main`.

## Build, test and package

Build on Debian 13 amd64 as described in [building.md](building.md), then complete
[testing.md](testing.md). A successful build is not a boot/install test. Retain
its logs outside Git. The first alpha version is `1.0.0-alpha.1`, with planned tag `v1.0.0-alpha.1`.
Keep it marked as a prerelease on GitHub.

After testing a unique build, promote it to `dist/erdos-amd64.iso`, then run:

```sh
python3 scripts/prepare-release.py --iso dist/erdos-amd64.iso
```

This verifies the ISO’s embedded installer policy and core-package retention,
extracts its package/version manifest, creates a source-only project ZIP, writes
checksums, and refreshes `docs/release.json` from the actual ISO. It requires
`xorriso` and `unsquashfs` in addition to Python 3. It leaves
`published` false so the site does not advertise nonexistent release downloads.
The source ZIP requires compiling helpers before using the optional updater;
generated executables are not silently bundled into a source archive.

Review and upload these assets to a **draft prerelease** on GitHub:

- `dist/erdos-amd64.iso`
- `dist/erdos-amd64.iso.sha256`
- `dist/erdos-amd64.packages`
- `dist/erdos-build-project.zip` and its `.sha256` sidecar
- `dist/SHA256SUMS`

Include the source revision, build/test environment, ISO checksum, known
limitations, public live credentials, and disk-installation behavior in the
release notes. Retain matching source and license notices for distributed GPL
packages; Debian package manifests alone are not corresponding-source archives.
Source versions can be identified using Debian package metadata and downloaded
from the matching Debian archives with source repositories enabled.

After those assets actually exist on a published release, set the chosen tag and
`published: true` in `docs/release.json`. Its existing filenames and digest must
still match those assets. The download buttons currently link directly to the `v1.0.0-alpha.1` ISO,
as configured in `index.html` and `assets/site.js`. Update both for a future release. Future builds use current Debian packages, so reusing a date does not
imply an identical ISO or checksum.

Checksums verify bytes, not publisher identity. If you add artifact signing,
document the public verification key and process separately.

To verify an ISO against the current source without writing release assets or
changing website metadata:

```sh
python3 scripts/prepare-release.py --verify-only --iso dist/erdos-amd64.iso
```

`build.sh` uses this same check before copying a new image to `dist/`.

## Gitman Pages

`docs/index.html` and `docs/guide.html` are standalone static pages. They use local
CSS, JavaScript, the supplied logo and actual screenshots. There is no Jekyll,
Node.js, npm, frontend build step, analytics or external font dependency.
`docs/.nojekyll` prevents Jekyll processing.

The repository is mirrored on GitHub and Gitman. Publish the contents of `docs/`
with Gitman Pages at <https://patx.gitman.io/erdos/>. Keep relative page and asset
links so the same source works under `/erdos/`. ISO downloads remain on GitHub
Releases.

Preview locally:

```sh
python3 -m http.server 8000 --directory docs
```

Open <http://localhost:8000/>. Relative paths also work under the project prefix
`/erdos/`. The user guide and release links work without JavaScript; build details
and the screenshot selector are optional enhancements. Keep release metadata
accurate when uploading a new image. Gitman Pages hosts the site; GitHub Releases
hosts the ISO.

## Checks before publication

Run `python3 scripts/check-project.py` and the Debian helper compilation check.
Review desktop and mobile rendering and keyboard navigation. The CI workflow is
read-only and source-only; it does not publish Pages, create a release or build an
ISO. Enable GitHub private vulnerability reporting if you want to use the private
reporting link in `SECURITY.md`.

- [GitHub Pages publishing sources](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
