# Prepare a GitHub release and Pages site

Repository: <https://github.com/patx/erdos>. Website:
<https://patx.gitman.io/erdos/>. These instructions prepare artifacts locally;
the release-packaging script does not commit, tag, push, upload or publish.
The current public release is [ErdOS 1 Alpha 3](https://github.com/patx/erdos/releases/tag/v1.0.0-alpha.3).
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
its logs outside Git. The checkout tracks current development; choose a new
version and tag when preparing a release. Keep published version directories immutable.

The build writes the current image to `dist/erdos-amd64.iso`. The previous X11
development ISO is retained locally as `dist/erdos-x11-dev.iso` for comparison;
it is not a new release asset. After testing, run:

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
The source ZIP requires compiling the compositor before using the optional updater;
generated executables are not silently bundled into a source archive.

Review and upload these assets to the versioned **Cloudflare R2** download directory:

- `dist/erdos-amd64.iso`
- `dist/erdos-amd64.iso.sha256`
- `dist/erdos-amd64.packages`
- `dist/erdos-build-project.zip` and its `.sha256` sidecar
- `dist/SHA256SUMS`

## Cloudflare R2 downloads

The Standard-storage bucket is `erdos-releases`, served through
<https://downloads.erd.sh/> with a minimum TLS version of 1.2. The Alpha 3 objects
are under `v1.0.0-alpha.3/`; the ISO URL is
<https://downloads.erd.sh/v1.0.0-alpha.3/erdos-amd64.iso>.
The website remains on Gitman Pages, and source code stays on both Git remotes.
The zone rule `erdos_alpha2_public_downloads` skips Security Level and Browser
Integrity Check only for GET/HEAD requests to the exact release download
paths for Alpha 2 and Alpha 3. Add each future version’s file paths to that rule before publishing its
links; keep other hosts, paths and methods outside the exception.

Use an S3-compatible multipart uploader for large files; Cloudflare documents
[rclone setup](https://developers.cloudflare.com/r2/examples/rclone/) and
[multipart uploads](https://developers.cloudflare.com/r2/objects/upload-objects/).
Scope its credentials to this bucket and keep them outside the repository.
Multipart transfer lets failed parts retry without restarting the whole ISO.
Upload all six prepared files into the same version directory. Keep released
version directories immutable; use a new version prefix for a replacement.

Download the completed ISO back and verify its SHA-256 against the local tested
image. Check the public ISO, checksum and source-archive URLs before changing
site links. No upload gateway or additional service is needed for downloads:
the custom domain serves objects directly from R2. Temporary upload access used
by maintainers must be removed after transfer and verification.

Create or update a **draft prerelease** on GitHub with the direct R2 ISO and
checksum links. The five small companion files may also be attached there; the
large ISO does not need to be a GitHub asset. Verify the final release notes and
publish as a prerelease only after the exact hosted image has passed validation.
No GitHub Actions build is required to host an already tested local image.

Include the source revision, build/test environment, ISO checksum, known
limitations, public live credentials, and disk-installation behavior in the
release notes. Retain matching source and license notices for distributed GPL
packages; Debian package manifests alone are not corresponding-source archives.
Source versions can be identified using Debian package metadata and downloaded
from the matching Debian archives with source repositories enabled.

After the R2 files are verified and the GitHub prerelease is published, set the chosen tag and
`published: true` in `docs/release.json`. Its existing filenames and digest must
still match those assets. Set `download_base_url` to the matching version directory. The hero button links directly to the R2 `v1.0.0-alpha.3` ISO; the bottom download
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
links so the same source works under `/erdos/`. ISO downloads use Cloudflare R2
at <https://downloads.erd.sh/>; release notes remain on GitHub Releases.

Preview locally:

```sh
python3 -m http.server 8000 --directory docs
```

Open <http://localhost:8000/>. Relative paths also work under the project prefix
`/erdos/`. The user guide and download links work without JavaScript.
Build details and checksums are available on the GitHub release page. Keep
release metadata accurate when uploading a new image. Gitman Pages hosts the site;
Cloudflare R2 hosts the ISO and matching download artifacts.

## Checks before publication

Run `python3 scripts/check-project.py` and the Debian helper compilation check.
Review desktop and mobile rendering and keyboard navigation. The CI workflow is
read-only and source-only; it does not publish Pages, create a release or build an
ISO. Enable GitHub private vulnerability reporting if you want to use the private
reporting link in `SECURITY.md`.

## Social preview

The landing page uses `docs/assets/og-image.png` for Open Graph and Twitter cards.
Regenerate it with `python3 scripts/render-social-card.py` on a development host
with Pillow and DejaVu Sans installed. The renderer uses the supplied logo and
`docs/assets/labwc-thumbnails.png`; its dependencies are not added to the ISO.
