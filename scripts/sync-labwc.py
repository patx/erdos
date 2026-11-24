#!/usr/bin/env python3
"""Check or explicitly import a committed labwc fork snapshot; never fetch or push."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent.parent
PIN = ROOT / 'vendor/labwc-fork.json'
VENDOR = ROOT / 'vendor/labwc'


def git(checkout, *args):
    return subprocess.check_output(['git', '-C', str(checkout), *args], stderr=subprocess.PIPE)


def commit(checkout, ref):
    return git(checkout, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}').decode().strip()


def exported(checkout, revision):
    """Keep all build sources; omit upstream hosting/ignore files and fork notes."""
    files = {}
    with tarfile.open(fileobj=io.BytesIO(git(checkout, 'archive', '--format=tar', revision))) as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if member.isdir():
                continue
            if (path.parts[0] == '.github' or path.name == '.gitignore'
                    or member.name == 'ERDOS.md'):
                continue
            if (path.is_absolute() or '..' in path.parts or not member.isfile()
                    or member.name in files or member.name == 'UPSTREAM'):
                raise ValueError('Unexpected fork archive entry: ' + member.name)
            files[member.name] = (archive.extractfile(member).read(), member.mode)
    return files


def current_files():
    files = {}
    for path in sorted(VENDOR.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlink in vendored source: ' + str(path))
        if path.is_file():
            files[str(path.relative_to(VENDOR))] = path.read_bytes()
    return files


def digest(files):
    result = hashlib.sha256()
    for name, data in sorted(files.items()):
        result.update(name.encode() + b'\0' + data)
    return result.hexdigest()


def assert_equal(actual, expected):
    different = sorted(name for name in actual.keys() | expected.keys()
                       if actual.get(name) != expected.get(name))
    if different:
        raise ValueError('Vendored files differ from the pinned fork; reconcile these changes in the fork first: '
                         + ', '.join(different))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, required=True, help='Local clone of the maintenance fork')
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--check', action='store_true', help='Read-only comparison with the recorded fork commit')
    modes.add_argument('--import', dest='import_snapshot', action='store_true', help='Explicitly replace the vendor snapshot and pin')
    parser.add_argument('--ref', help='Committed fork ref to import (defaults to the recorded commit)')
    parser.add_argument('--base', help='Exact upstream commit incorporated by that fork ref')
    parser.add_argument('--version', help='Corresponding upstream labwc version')
    args = parser.parse_args()
    if args.check and any((args.ref, args.base, args.version)):
        parser.error('--check uses only the recorded pin; update it with an explicit --import')
    if args.ref and not (args.base and args.version):
        parser.error('--ref requires both --base and --version, even when the upstream base is unchanged')
    if bool(args.base) != bool(args.version):
        parser.error('--base and --version must be supplied together')
    pin = json.loads(PIN.read_text())
    checkout = args.checkout.resolve(strict=True)
    revision = commit(checkout, args.ref or pin['fork_commit'])
    base = args.base or pin['upstream_commit']
    version = args.version or pin['upstream_version']
    if not re.fullmatch(r'[0-9a-f]{40}', base):
        raise ValueError('Use the exact 40-character upstream commit')
    if commit(checkout, base) != base:
        raise ValueError('Upstream base is not a commit')
    git(checkout, 'merge-base', '--is-ancestor', base, revision)
    meson = git(checkout, 'show', base + ':meson.build').decode()
    declared = re.search(r"\bversion\s*:\s*'([^']+)'", meson)
    if not declared or declared[1] != version:
        raise ValueError('Version does not match the upstream base meson.build')
    current = current_files()
    original_note = current.pop('UPSTREAM')
    old = exported(checkout, pin['fork_commit'])
    assert_equal(current, {name: data for name, (data, _) in old.items()})
    if args.check:
        if digest({**current, 'UPSTREAM': original_note}) != pin['vendor_tree_sha256']:
            raise ValueError('Vendored provenance note/tree hash differs from the recorded pin')
        print('PASS: vendored labwc matches fork ' + pin['fork_commit'] + '; upstream ' + version + ' unchanged')
        return
    if git(checkout, 'status', '--porcelain').strip():
        raise ValueError('Commit or clear fork working-tree changes before importing a committed snapshot')
    files = exported(checkout, revision)
    note = original_note.decode()
    for key, value in (('Version', version), ('Commit', base)):
        note, count = re.subn(r'^' + key + r': .*$', key + ': ' + value, note, flags=re.MULTILINE)
        if count != 1:
            raise ValueError('Unexpected UPSTREAM note format')
    payload = {name: data for name, (data, _) in files.items()}
    payload['UPSTREAM'] = note.encode()
    updated = {**pin, 'upstream_commit': base, 'upstream_version': version,
               'fork_commit': revision, 'fork_ref': args.ref or pin['fork_ref'],
               'vendor_tree_sha256': digest(payload)}
    work = ROOT / 'work'
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='labwc-import-', dir=work) as temporary:
        temporary = Path(temporary)
        staged = temporary / 'labwc'
        staged.mkdir()
        for name, data in payload.items():
            path = staged / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o755 if name in files and files[name][1] & 0o111 else 0o644)
        staged_pin = temporary / 'pin.json'
        staged_pin.write_text(json.dumps(updated, indent=2) + '\n')
        backup = temporary / 'previous'
        os.replace(VENDOR, backup)
        try:
            os.replace(staged, VENDOR)
            os.replace(staged_pin, PIN)
        except BaseException:
            if VENDOR.exists():
                shutil.rmtree(VENDOR)
            os.replace(backup, VENDOR)
            raise
    print('Imported fork ' + revision + '; review git diff and validate before committing')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
