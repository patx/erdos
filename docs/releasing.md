# Prepare a GitHub release and Pages site

Repository: <https://github.com/patx/erdos>. Website:
<https://patx.gitman.io/erdos/>. These instructions prepare artifacts locally;
the release-packaging script does not commit, tag, push, upload or publish.
The current public release is [ErdOS 1 Alpha 2](https://github.com/patx/erdos/releases/tag/v1.0.0-alpha.2).
Both source remotes use `main`: GitHub at the URL above and Gitman at
<https://gitman.io/git/patx/erdos>.

## Source repository

Commit source, documentation, licenses, branding and the pinned third-party sources.
Keep `work/`, `dist/`, `downloads/`, `validation/`, `release-tools/`, disk images,
logs and local credentials out of Git. Inspect `git status --short` and
`git status --ignored --short` before staging. Do not add ignored artifacts with
`git add -f`. The generated source ZIP uses an allowlist and excludes local test
fixtures and generated binaries.

The default branch is `main` on both remotes. Keep source changes synchronized
with GitHub (`origin`) and Gitman (`gitman`); pushing source does not create or
upload a release asset.

## Build, test and package

Build on Debian 13 amd64 as described in [building.md](building.md), then complete
[testing.md](testing.md). A successful build is not a boot/install test. Retain
its logs outside Git. The current alpha version is `1.0.0-alpha.2`, with tag `v1.0.0-alpha.2`.
Keep it marked as a prerelease on GitHub.

After testing a unique build, promote it to `dist/erdos-amd64.iso`, then run:

```sh
python3 scripts/prepare-release.py --iso dist/erdos-amd64.iso
```

This verifies the ISO’s embedded installer policy and core-package retention,
extracts its package/version manifest, creates a source-only project ZIP, writes
checksums, and refreshes `docs/release.json` from the actual ISO. It requires
`xorriso` and `unsquashfs` in addition to Python 3. It leaves
`published` false and clears the tag for the newly prepared image. Restore the
actual published tag and status only after its assets are available. Packaging
a future build must not be mistaken for publishing it.
The source ZIP requires compiling helpers before using the optional updater;
generated executables are not silently bundled into a source archive.

### Build Alpha 2 on GitHub

The manual run of `.github/workflows/check.yml` also builds the pinned Alpha 2
tag, `v1.0.0-alpha.2` (`97ea861cc1e657f8189131f80dd673304a76cdd1`). Push and
pull-request runs remain source checks only. While the release is pending, the
workflow changes are on `build-alpha2-remote`, keeping the current public site
unchanged. Run the existing **Source checks** workflow with that branch selected:

```sh
gh workflow run check.yml --repo patx/erdos --ref build-alpha2-remote
```

GitHub Actions must be enabled and the account's Actions billing lock cleared
before a runner can start. The workflow uses the ephemeral repository token;
no personal token or added repository secret is required. A disposable Ubuntu
runner makes space by removing unused SDKs, then runs live-build in the pinned
official Debian 13 container. Build dependencies stay outside the ISO.

The job uploads directly from GitHub to an **unpublished draft prerelease**;
it does not transfer the ISO from the maintainer's laptop. It verifies the
server's SHA-256 and size for each asset and refuses to replace a published
release. In addition to the six normal assets, `erdos-build.json` records the
actual source revision, workflow run, container image and new ISO identity.
`SHA256SUMS` also covers this build record. Build logs remain in the Actions run.

A clean rebuild is not byte-identical to the earlier local ISO. The workflow
does not boot or install it. Download the draft image, run fresh VM validation
and measurements, update the website's release metadata and results, and
refresh the source archive/checksums before publication. Do not attach the old
local checksum or claim that its VM measurements tested the remote image.
Publish only after those checks; then synchronize `main` on both remotes.

The upload tool can check a destination without modifying it:

```sh
python3 scripts/upload-draft-release.py --directory . --repository patx/erdos \
  --tag v1.0.0-alpha.2 --check-only
```

It requires GitHub CLI authentication. Upload mode additionally requires the
prepared assets, remote build record and build-specific `--notes` file. It
always leaves the release in draft form.

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
still match those assets. The hero button links directly to the `v1.0.0-alpha.2` ISO; the bottom download
section links to its release page. Update both links in `index.html` for a future
release, together with the version text and release metadata. Future builds use current Debian packages, so reusing a date does not
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
CSS, the supplied logo and actual screenshots. There is no Jekyll,
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
`/erdos/`. The user guide and download links work without JavaScript.
Build details and checksums are available on the GitHub release page. Keep
release metadata accurate when uploading a new image. Gitman Pages hosts the site; GitHub Releases
hosts the ISO.

## Checks before publication

Run `python3 scripts/check-project.py` and the Debian helper compilation check.
Review desktop and mobile rendering and keyboard navigation. Push and pull-request
CI runs are read-only source checks. A manual run also builds Alpha 2 and uploads
verified draft assets as described above; it never publishes the release or Pages.
Enable GitHub private vulnerability reporting if you want to use the private
reporting link in `SECURITY.md`.

## Social preview

The landing page uses `docs/assets/og-image.png` for Open Graph and Twitter cards.
Regenerate it with `python3 scripts/render-social-card.py` on a development host
with Pillow and DejaVu Sans installed. The renderer uses the supplied logo and
`docs/assets/desktop-hero.png`; its dependencies are not added to the ISO.
