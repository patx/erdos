# Updating an installed ErdOS desktop

Reinstalling is not necessary for desktop updates. On an existing **Alpha 3
labwc/Wayland** installation, download the updater and run it as your normal user:

```sh
curl -fsSL https://downloads.erd.sh/update.sh -o erdos-update.sh
sh erdos-update.sh
```

The minimal ISO does not include curl. If it is absent, use Python 3, which is
already installed:

```sh
python3 - <<'PYTHON'
from pathlib import Path
from urllib.request import urlopen
with urlopen('https://downloads.erd.sh/updates/erdos-update.py', timeout=60) as response:
    Path('erdos-update.py').write_bytes(response.read())
PYTHON
python3 erdos-update.py
```

It shows the available version and files, asks before installing, then requests
sudo authorization. Log out of the desktop and back in afterward. The current
update includes the Settings redesign and system dark-mode preference, matching
the tested ISO selected for Alpha 4. The updater installs itself after its first
successful update; it is hosted separately from the unchanged ISO. It adds no Debian packages or background service.

For later updates, use the same command or the installed helper:

```sh
erdos-update --check
erdos-update
```

`--check` only reports changes. `--yes` skips the update confirmation, but does
not bypass sudo authorization. Downloads use HTTPS; the payload's SHA-256 and
individual file hashes are checked before installation. The manifest is served
by the same trusted host; hashes detect corruption, rather than providing an
independent release signature.

## What is preserved

The updater replaces only listed ErdOS desktop helpers, their Python modules,
the Settings launcher, portal selection, background service definition and
ErdOS version label. It never invokes package installation, upgrade, removal or
autoremove. It leaves the running compositor alone until your next session.

Your home directory, shortcuts, menu, startup apps, default apps, appearance,
network connections and other personal settings are untouched. Kernel, firmware,
drivers, DKMS, module options, audio configuration, webcam fixes, bootloader,
power policy and APT sources are outside the update's allowed paths. This is
intended to preserve machine-specific MacBook fixes.

If an ErdOS-managed file itself contains a local fix, the updater stops **before
changing anything** and lists the conflicting files. Review those changes
manually rather than removing the hardware fix. Updates from the old X11 builds
or a different compositor build are refused; this is not an X11 migration tool.
Debian security/package updates remain a separate APT operation.

## Backup and recovery

Every changed file is backed up under a root-owned directory inside
`/var/lib/erdos/updates/`. The updater prints its exact rollback command:

```sh
sudo erdos-update --rollback /var/lib/erdos/updates/UPDATE-BACKUP-DIRECTORY
```

Use the actual path it prints. Rollback restores contents, modes and ownership,
and removes files introduced by that update. It refuses to overwrite files
modified since the update. Roll back the latest update first. A failed write
triggers automatic restoration. If power is lost during installation, the next
update refuses to proceed and prints the interrupted backup's rollback command.
Do not delete a backup while an update is in progress. Old completed backups may
be removed manually when no longer needed.

## Publishing future desktop updates

Maintainers prepare an immutable versioned bundle from the reviewed working tree:

```sh
python3 scripts/build-desktop-update.py 2026.11.22-settings.1 --sequence 2026112201
```

The current bundle is approximately 59 KB compressed. For the next update, choose
a new version and a strictly increasing sequence, and pass every previously
published bundle with `--previous PATH/desktop.json.gz`. This retains accepted
previous-file hashes, including users who skip releases. Keep these small bundles
as release artifacts. The initial baseline is Alpha 3's source revision; use
`--baseline REVISION` only when intentionally supporting another known baseline.

Upload `dist/updates/VERSION/desktop.json.gz` to
`erdos-releases/updates/VERSION/desktop.json.gz` in Cloudflare R2. Upload the
prepared `erdos-update.py` and `update.sh` into `updates/`, and the same shell
script at the bucket root as `update.sh`. Verify their public contents, then
extend the exact-path GET/HEAD download exception to the new versioned bundle, then
publish `dist/updates/latest.json` to `updates/latest.json` **last**. Verify the
public latest manifest and bundle checksum and run `erdos-update --check` against
an installed test system. Never reuse a published version for changed contents.
Do not cache the mutable latest manifest or bootstrap script across publications.

The bundle records the required compositor hash. Compositor/package transitions,
removals and configuration migrations need an explicitly designed and tested
migration, not an expansion into arbitrary system files or shell install hooks.
