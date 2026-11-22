#!/usr/bin/env python3
"""Update ErdOS-owned desktop files without changing Debian or user configuration."""
import argparse
import base64
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import subprocess
import sys
import tempfile
import urllib.request
import urllib.parse

BASE = 'https://downloads.erd.sh/updates/'
STATE = Path('/var/lib/erdos/updates')
LIMIT = 8 * 1024 * 1024
EXACT = {
    'etc/erdos-release',
    'usr/share/applications/erdos-settings.desktop',
    'usr/share/xdg-desktop-portal/labwc-portals.conf',
    'usr/lib/systemd/user/erdos-background.service',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def allowed(name):
    p = PurePosixPath(name)
    if str(p) != name or p.is_absolute() or '..' in p.parts:
        return False
    return name in EXACT or (len(p.parts) == 4 and p.parts[:3] == ('usr', 'local', 'bin')
                             and re.fullmatch(r'erdos-[a-z-]+', p.name)) or (
        len(p.parts) == 5 and p.parts[:4] == ('usr', 'local', 'lib', 'erdos')
        and p.suffix == '.py' and re.fullmatch(r'[a-z_]+\.py', p.name))


def destination(name):
    if not allowed(name):
        raise ValueError(f'Not an ErdOS desktop update path: {name}')
    p = Path('/') / name
    for component in (p, *p.parents):
        if component.is_symlink():
            raise ValueError(f'Refusing a symlink: {component}')
    if p.exists() and not p.is_file():
        raise ValueError(f'Not a regular file: {p}')
    return p


def download(url):
    if not url.startswith(BASE) or urllib.parse.urlsplit(url).scheme != 'https':
        raise ValueError('Update URL must use the ErdOS HTTPS update host.')
    request = urllib.request.Request(url, headers={'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(request, timeout=60) as response:
        if not response.url.startswith(BASE):
            raise ValueError('Update redirected away from the ErdOS update host.')
        data = response.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError('Update exceeds the size limit.')
    return data


def bundle(raw):
    # Bound decompression as well as the network response. No archive paths or
    # executable installation hooks are extracted or run.
    import io
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        unpacked = stream.read(LIMIT + 1)
    if len(unpacked) > LIMIT:
        raise ValueError('Unpacked update exceeds the size limit.')
    data = json.loads(unpacked)
    if data['schema'] != 1 or not re.fullmatch(r'[a-zA-Z0-9._-]+', data['version']):
        raise ValueError('Unsupported update format/version.')
    if not isinstance(data['sequence'], int) or data['sequence'] < 1:
        raise ValueError('Invalid update sequence.')
    names = set()
    for item in data['files']:
        name = item['path']
        if not allowed(name) or name in names or item['mode'] not in (0o644, 0o755):
            raise ValueError(f'Invalid update entry: {name}')
        names.add(name)
        content = base64.b64decode(item['data'], validate=True)
        if digest(content) != item['sha256']:
            raise ValueError(f'Update content checksum mismatch: {name}')
        if not all(re.fullmatch(r'[0-9a-f]{64}', h) for h in item['previous']):
            raise ValueError('Invalid previous-file checksum.')
    if not names or len(names) > 100:
        raise ValueError('Invalid update file count.')
    return data


def compatible(data):
    release = {}
    for line in Path('/etc/os-release').read_text().splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            release[k] = v.strip('"')
    if release.get('ID') != 'debian' or release.get('VERSION_ID') != '13':
        raise ValueError('This update requires Debian 13.')
    if not Path('/etc/erdos-release').is_file() or platform.machine() != 'x86_64':
        raise ValueError('An existing amd64 ErdOS installation is required.')
    # This channel updates the desktop, never the kernel, firmware or compositor.
    # A release requiring a different compositor needs a separate migration.
    if digest(Path('/usr/local/bin/labwc').read_bytes()) != data['labwc_sha256']:
        raise ValueError('This desktop update requires the Alpha 3 labwc build; no files were changed.')
    if (STATE / 'current.json').exists():
        current = json.loads((STATE / 'current.json').read_text())
        if current['sequence'] > data['sequence']:
            raise ValueError('Refusing to downgrade a newer installed desktop update.')


def plan(data):
    changed = []
    conflicts = []
    for item in data['files']:
        path = destination(item['path'])
        if path.exists():
            st = path.stat()
            checksum = digest(path.read_bytes())
            if checksum == item['sha256'] and stat.S_IMODE(st.st_mode) == item['mode']:
                continue
            if checksum not in [item['sha256'], *item['previous']]:
                conflicts.append(str(path))
                continue
        changed.append(item)
    if conflicts:
        raise ValueError('Locally modified ErdOS files would be overwritten. Nothing changed.\n'
                         + '\n'.join(conflicts) + '\nKeep these fixes and review the update manually.')
    return changed


def atomic(path, content, mode=0o644, uid=0, gid=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.erdos-update-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
            os.fchown(stream.fileno(), uid, gid)
        os.replace(name, path)
        folder = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(folder)
        finally:
            os.close(folder)
    finally:
        Path(name).unlink(missing_ok=True)


def journal(path, value):
    atomic(path, (json.dumps(value, indent=2) + '\n').encode(),
           0o644 if path == STATE / 'current.json' else 0o600)


def restore(backup, force=False):
    backup = backup.resolve(strict=True)
    if backup.parent != STATE or backup.stat().st_uid != 0:
        raise ValueError('Choose a root-owned backup directly inside /var/lib/erdos/updates/.')
    record = json.loads((backup / 'journal.json').read_text())
    current = json.loads((STATE / 'current.json').read_text()) if (STATE / 'current.json').exists() else None
    if not force and record['status'] == 'complete' and (not current or current.get('backup') != str(backup)):
        raise ValueError('Roll back the most recent desktop update first.')
    if record['status'] == 'rolled-back':
        raise ValueError('This update is already rolled back.')
    # Check all files before restoring any: rollback must not erase later fixes.
    for item in record['files']:
        p = destination(item['path'])
        if not force:
            checksum = digest(p.read_bytes()) if p.exists() else None
            accepted = [item['installed_sha256']]
            if record['status'] == 'applying':
                accepted.append(digest((backup / 'files' / item['path']).read_bytes()) if item['existed'] else None)
            if checksum not in accepted:
                raise ValueError(f'Changed since this update; refusing rollback: {p}')
    for item in reversed(record['files']):
        p = destination(item['path'])
        if item['existed']:
            content = (backup / 'files' / item['path']).read_bytes()
            atomic(p, content, item['mode'], item['uid'], item['gid'])
        else:
            p.unlink(missing_ok=True)
    if record['previous_state'] is None:
        (STATE / 'current.json').unlink(missing_ok=True)
    else:
        journal(STATE / 'current.json', record['previous_state'])
    record['status'] = 'rolled-back'
    journal(backup / 'journal.json', record)
    print('Restored desktop files. Log out of the desktop and back in.')


def apply(raw):
    data = bundle(raw)
    compatible(data)
    for pending in STATE.glob('*/journal.json'):
        if json.loads(pending.read_text())['status'] == 'applying':
            raise ValueError(f'An update was interrupted. First run: sudo erdos-update --rollback {pending.parent}')
    changes = plan(data)
    if not changes:
        print('Already up to date. No files changed.')
        return
    backup = Path(tempfile.mkdtemp(prefix=data['version'] + '-', dir=STATE))
    previous = json.loads((STATE / 'current.json').read_text()) if (STATE / 'current.json').exists() else None
    record = {'status': 'preparing', 'version': data['version'], 'previous_state': previous, 'files': []}
    for item in changes:
        path = destination(item['path'])
        entry = {'path': item['path'], 'existed': path.exists(), 'installed_sha256': item['sha256']}
        if path.exists():
            st = path.stat()
            entry.update(mode=stat.S_IMODE(st.st_mode), uid=st.st_uid, gid=st.st_gid)
            target = backup / 'files' / item['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic(target, path.read_bytes(), 0o600)
        record['files'].append(entry)
    record['status'] = 'applying'
    journal(backup / 'journal.json', record)
    try:
        for item in changes:
            # Recheck paths immediately before each atomic replacement.
            atomic(destination(item['path']), base64.b64decode(item['data']), item['mode'])
        journal(STATE / 'current.json', {'version': data['version'], 'sequence': data['sequence'],
                                        'bundle_sha256': digest(raw), 'backup': str(backup)})
        record['status'] = 'complete'
        journal(backup / 'journal.json', record)
    except BaseException:
        restore(backup, force=True)
        raise
    print(f'Updated ErdOS desktop to {data["version"]}.')
    print(f'Backup: {backup}')
    print(f'Rollback: sudo erdos-update --rollback {backup}')
    print('Log out of the desktop and back in to use the updated files.')
    print('Drivers, kernel, firmware, system services and personal configuration were left alone.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Show available changes without installing')
    parser.add_argument('--yes', action='store_true', help='Skip the update confirmation')
    parser.add_argument('--rollback', type=Path, metavar='BACKUP', help='Restore a saved desktop update')
    parser.add_argument('--apply-bundle', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.rollback or args.apply_bundle:
        if os.geteuid() != 0:
            parser.error('This operation requires sudo.')
        STATE.mkdir(parents=True, exist_ok=True, mode=0o755)
        if any(p.is_symlink() for p in (STATE, *STATE.parents)) or STATE.stat().st_uid != 0 or STATE.stat().st_mode & 0o022:
            raise ValueError('Unsafe update state directory.')
        with (STATE / 'lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.rollback:
                restore(args.rollback)
            else:
                raw = args.apply_bundle.read_bytes()
                if len(raw) > LIMIT:
                    raise ValueError('Update exceeds the size limit.')
                apply(raw)
        return
    manifest = json.loads(download(BASE + 'latest.json'))
    if manifest['schema'] != 1 or not re.fullmatch(r'[a-zA-Z0-9._-]+', manifest['version']):
        raise ValueError('Invalid update manifest.')
    raw = download(BASE + manifest['version'] + '/desktop.json.gz')
    if digest(raw) != manifest['sha256']:
        raise ValueError('Downloaded update checksum mismatch. Nothing changed.')
    data = bundle(raw)
    if data['version'] != manifest['version']:
        raise ValueError('Update manifest and payload disagree.')
    compatible(data)
    changes = plan(data)
    print(f'ErdOS desktop update: {data["version"]} ({len(raw):,} bytes downloaded)')
    for item in changes:
        print('  /' + item['path'])
    print('Personal settings, drivers and Debian packages are preserved.')
    if args.check or not changes:
        print('No files changed.' if args.check else 'Already up to date.')
        return
    if not args.yes:
        with open('/dev/tty', 'r+') as tty:
            tty.write('Install this desktop update? [y/N] ')
            tty.flush()
            if tty.readline().strip().lower() not in ('y', 'yes'):
                print('Cancelled. No files changed.')
                return
    with tempfile.TemporaryDirectory(prefix='erdos-update-') as temp:
        path = Path(temp) / 'desktop.json.gz'
        path.write_bytes(raw)
        command = [sys.executable, str(Path(__file__).resolve()), '--apply-bundle', str(path)]
        if os.geteuid() != 0:
            command.insert(0, 'sudo')
        subprocess.run(command, check=True)


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print(f'Update stopped: {error}', file=sys.stderr)
        sys.exit(1)
