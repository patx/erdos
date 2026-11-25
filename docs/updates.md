# Updating ErdOS

Beta 2 packages the desktop/Settings/Twig, pinned labwc with
static wlroots, and archive key as **erdos-desktop**, **erdos-labwc** and
**erdos-archive-keyring**. These adopt existing files rather than adding another
desktop, update daemon or signing utility. Debian and Mozilla still maintain
their own packages. Beta 2 is a prerelease, not a stable ErdOS 1 release.
Beta 1 and earlier images require the checked migration below.

## Package-managed installations

Use Settings → Software, or:

```sh
sudo apt update
sudo apt upgrade
```

Review the proposed changes. Log out and back in after desktop/compositor
updates; the running session is not forcibly restarted. About shows the base
image separately from the installed desktop package, source revision, labwc,
wlroots and Twig. It also detects a running compositor whose bytes differ from
the installed version. Debian package changes do not rewrite your personal
menu, shortcuts, startup applications or machine-specific driver configuration.

The repository is `https://downloads.erd.sh/apt/`, suite
`trixie-erdos`. Its deb822 source uses `Signed-By` with the dedicated
`/usr/share/keyrings/erdos-archive-keyring.asc`. Its key is not trusted globally.
APT preferences allow only the three named ErdOS packages from Origin `ErdOS`;
other packages from that origin have priority -1. No `trusted=yes`, signature
bypass or new background service is used.

Archive key fingerprint:

```text
6AF1 B019 608C A9CC A7EA 32E3 6AC6 5596 E9E4 F83D
```

## Existing Beta/development installations

Migration is explicit. Use a reviewed checkout containing the packaging tools
and public key; do not pipe an unverified remote script into sudo. Git is not
required on the installed desktop: the matching release source ZIP can be
extracted with Python already included in ErdOS:

```sh
python3 - <<'PYTHON'
from urllib.request import urlretrieve
base = 'https://downloads.erd.sh/v1.0.0-beta.2/'
for name in ('erdos-build-project.zip', 'erdos-build-project.zip.sha256'):
    urlretrieve(base + name, name)
PYTHON
sha256sum -c erdos-build-project.zip.sha256
python3 -m zipfile -e erdos-build-project.zip erdos-update-source
cd erdos-update-source/erdos
```

Checksums detect corruption; obtain the files from the intended release and
review the migration code and pinned public key before administrative execution.
First:

```sh
python3 scripts/enable-apt-updates.py
```

This is a dry run. It accepts the known labwc-based layout, checks legacy file
hashes and compositor provenance, and refuses locally modified managed files or
unexpected symlinks. If it reports a conflict, keep the local fix and review it;
do not delete it to force migration. Older compositor/X11 layouts are unsupported.

After reviewing the plan:

```sh
sudo python3 scripts/enable-apt-updates.py --apply
```

It installs the pinned public key/source, lets APT verify the signed archive and
asks APT to install the three packages with removals forbidden. Only after a
successful installation are checked `/usr/local` copies moved to a root-owned
backup under `/var/lib/erdos/apt-migration/`. This prevents old executables from
shadowing the package-managed `/usr` versions. Known old command paths receive
administrator-created compatibility symlinks to `/usr/bin`; existing absolute
menu/startup references keep working and follow future package updates. No files
under `/usr/local` are owned by the Debian packages. Existing user homes, driver/DKMS
fixes, bootloader, kernel, firmware and network configuration are not migrated.
APT may ask about existing system defaults: keep local changes when appropriate.
Then log out and back in. Window-button defaults are left-aligned for new users;
existing users can choose the position in Appearance.

If APT fails or you cancel, legacy files remain in place. Read the terminal
output, resolve the package error and rerun the checked migration. Retain its
backup until the new desktop has been tested. There is no automatic downgrade
or promise that arbitrary older configurations can be restored over newer ones.

## Maintainer build and publication

Versions live in `packaging/versions.json`. Increment `package_version` before
publishing different package bytes, including Settings-only changes. Use Debian prerelease ordering (for example `1.0.0~beta.2`). Do not
label a development candidate as stable. The compositor version remains 0.9.7
and bundled wlroots remains 0.19.2 until deliberately updated in the maintenance
fork. Build-only compiler/signing tools are not installed into the desktop.

```sh
./scripts/build-components-in-docker.sh
```

This builds the /usr-prefix compositor and exports verified `.deb` files, an
exact source snapshot and component provenance into ignored `dist/packages/`. To repackage Settings/defaults
without recompiling unchanged compositor source:

```sh
./scripts/build-components-in-docker.sh --reuse
```

The reusable compositor is checked against its binary digest, prefix and pinned
source hashes. The resulting desktop package records the actual current source
revision (marked dirty when applicable) and full public-source digest.

Create the signed archive with a dedicated private signing home outside Git:

```sh
python3 scripts/make-apt-repository.py \
  --gnupg-home "$HOME/.local/share/erdos/apt-signing" \
  --signing-key 6AF1B019608CA9CCA7EA32E36AC65596E9E4F83D
```

`dist/apt/` contains the three binary packages, a native corresponding-source
package with build instructions and vendored sources, Packages/Sources indexes,
SHA-256 by-hash indexes, Release/Release.gpg and InRelease. APT authenticates the
signed metadata, which authenticates index hashes and package/source hashes.
Source repositories can be enabled by adding `deb-src` to the source's Types.

Upload immutable pool/by-hash objects first, ordinary indexes next, then signed
release metadata with **InRelease last**. Never replace an existing package or
source object with different bytes. Keep old server-side pool/by-hash objects
so clients holding earlier metadata can finish downloading. Mutable indexes and
release metadata must not be served with an immutable cache policy.
`scripts/upload-apt-repository.py` implements this ordering for the temporary,
scoped upload endpoint used by maintainers. Its JSON acknowledgement must include
`ok: true` and the exact stored `sha256`, including for existing objects. This
prevents a stale endpoint deployment from acknowledging a different manifest.
It carries no embedded credentials.

Signed metadata expires after **30 days**. Refresh it before expiry even when
no packages change:

```sh
python3 scripts/make-apt-repository.py --refresh \
  --gnupg-home "$HOME/.local/share/erdos/apt-signing" \
  --signing-key 6AF1B019608CA9CCA7EA32E36AC65596E9E4F83D
```

This keeps package/source/index bytes unchanged and re-signs only release
metadata. Republish it in the same order. Never disable APT's expiry or signature
checks to hide an expired key, metadata or incorrect system clock.

The dedicated key created for initial setup is filesystem-protected in the
0700 signing directory, initially without a passphrase for the unattended setup.
Back up its secret key and revocation certificate securely/offline, restrict
access, and add a passphrase with `gpg --homedir ... --edit-key ...` / `passwd`
when choosing the long-term signing arrangement. Neither belongs in Git,
Cloudflare, an ISO, a source archive, build containers or public artifacts.
The initial key expires in November 2028. Rotate before expiry by shipping a
keyring trusting both keys while metadata is still signed by the old valid key;
switch signing only after clients can receive the updated keyring. Do not change
a fingerprint in the bootstrap instructions without independent review.

## Legacy updater

The earlier hosted `erdos-update` bundle is frozen for its original Alpha 3
baseline. Its script and existing rollback backups are unchanged. It is not the
new package updater and does not support adopting the current development
compositor. New bundles are no longer generated with `build-desktop-update.py`.
