#!/usr/bin/env python3
"""Verify an existing ISO and prepare local release assets. Never publish or commit."""
import argparse
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

from project_files import public_files

ROOT = Path(__file__).resolve().parent.parent
CORE = {'desktop-file-utils', 'network-manager', 'systemd-timesyncd', 'bluez', 'libspa-0.2-bluetooth', 'ca-certificates', 'debian-archive-keyring', 'sudo', 'sakura', 'firefox', 'pcmanfm', 'libinput10', 'libxkbcommon0', 'gsettings-desktop-schemas', 'dconf-gsettings-backend', 'xdg-desktop-portal-gtk', 'libseat1', 'swaybg', 'grim', 'slurp', 'wlr-randr', 'xwayland', 'python3', 'python3-gi', 'erdos-desktop', 'erdos-labwc', 'erdos-archive-keyring', 'gir1.2-gtk-3.0', 'procps'}


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f'{args[0]} failed: {result.stderr.strip()}')
    return result.stdout


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def archive_file(initrd, wanted):
    """Read one regular file from a gzip/newc initrd without extracting paths."""
    with gzip.open(initrd, 'rb') as stream:
        while True:
            header = stream.read(110)
            if len(header) != 110 or header[:6] not in {b'070701', b'070702'}:
                raise ValueError('Invalid or truncated Debian Installer initrd')
            size = int(header[54:62], 16)
            namesize = int(header[94:102], 16)
            if not 0 < namesize <= 4096:
                raise ValueError('Invalid initrd filename length')
            name = stream.read(namesize).rstrip(b'\0').decode('utf-8')
            stream.read(-(110 + namesize) % 4)
            if name == 'TRAILER!!!':
                raise ValueError(f'Installer initrd is missing {wanted}')
            if name.removeprefix('./') == wanted:
                mode = int(header[14:22], 16)
                if mode & 0o170000 != 0o100000 or size > 1024 * 1024:
                    raise ValueError('Installer preseed must be a small regular file')
                data = stream.read(size)
                if len(data) != size:
                    raise ValueError('Truncated installer preseed')
                return data
            stream.seek(size + (-size % 4), 1)


def extract(iso, source, target):
    run('xorriso', '-osirrox', 'on', '-indev', str(iso), '-extract', source, str(target))


def verify_image(iso):
    with tempfile.TemporaryDirectory(prefix='erdos-release-') as directory:
        temporary = Path(directory)
        extract(iso, '/live/filesystem.packages', temporary / 'packages')
        packages = (temporary / 'packages').read_bytes()
        installed = {line.split()[0].split(':')[0] for line in packages.decode().splitlines() if line.strip()}
        if {'chromium', 'firefox-esr', 'openbox', 'xserver-xorg-core', 'scrot', 'hsetroot', 'nm-connection-editor', 'pulsemixer'} & installed:
            raise ValueError('ISO contains a removed utility, replaced browser or legacy X11 desktop component')
        if missing := CORE - installed:
            raise ValueError(f'ISO package manifest is missing required packages: {sorted(missing)}')
        removals = run('xorriso', '-indev', str(iso), '-find', '/live', '-name', 'filesystem.packages-remove')
        if '/live/filesystem.packages-remove' in removals:
            extract(iso, '/live/filesystem.packages-remove', temporary / 'remove')
            removed = {line.split()[0].split(':')[0] for line in (temporary / 'remove').read_text().splitlines() if line.strip()}
            if forbidden := CORE & removed:
                raise ValueError(f'Installer would remove required packages: {sorted(forbidden)}')
        extract(iso, '/install/initrd.gz', temporary / 'initrd.gz')
        installer_includes = ROOT / 'config/includes.installer'
        for source in sorted(installer_includes.rglob('*')):
            if source.is_file():
                relative = str(source.relative_to(installer_includes))
                if archive_file(temporary / 'initrd.gz', relative) != source.read_bytes():
                    raise ValueError(f'ISO installer configuration differs from source: {relative}')
        report = subprocess.run(['xorriso', '-indev', str(iso), '-find', '/live/filesystem.squashfs', '-exec', 'report_lba', '--'], capture_output=True, text=True, check=True)
        match = re.search(r'File data lba:\s*\d+\s*,\s*(\d+)\s*,', report.stdout + report.stderr)
        if not match:
            raise ValueError('Cannot locate the ISO live filesystem')
        offset = str(int(match[1]) * 2048)
        # Repacking an extracted tree must preserve privileged-file metadata.
        critical = ('usr/bin/sudo', 'etc/sudo.conf', 'etc/sudoers',
                    'usr/lib/systemd/systemd', 'usr/bin/systemctl',
                    'usr/lib/erdos/configure-apt')
        listing = subprocess.check_output(['unsquashfs', '-lln', '-o', offset,
            str(iso), *critical], text=True, stderr=subprocess.PIPE)
        checked = set()
        for line in listing.splitlines():
            fields = line.split(None, 5)
            if len(fields) != 6 or not fields[0].startswith('-'):
                continue
            name = fields[5].removeprefix('squashfs-root/')
            if name not in critical:
                continue
            if fields[1].split('/')[0] != '0':
                raise ValueError(f'Privileged ISO file is not root-owned: {name}')
            if name == 'usr/bin/sudo' and fields[0][3] != 's':
                raise ValueError('ISO sudo executable has lost its setuid permission')
            checked.add(name)
        if checked != set(critical):
            raise ValueError(f'ISO is missing privileged runtime files: {sorted(set(critical)-checked)}')
        # Keep live-media APT metadata, but reject downloaded build indexes and DEBs.
        apt_files = subprocess.check_output(['unsquashfs', '-ll', '-o', offset, str(iso),
            'var/lib/apt/lists', 'var/cache/apt'], text=True, stderr=subprocess.PIPE)
        apt_bytes = 0
        for line in apt_files.splitlines():
            fields = line.split(None, 5)
            if len(fields) == 6 and fields[0].startswith('-'):
                apt_bytes += int(fields[2])
                if fields[5].endswith('.deb'):
                    raise ValueError('ISO contains downloaded APT package archives')
        if apt_bytes > 8 * 1024 * 1024:
            raise ValueError(f'ISO carries excessive APT build cache: {apt_bytes} bytes')
        includes = ROOT / 'config/includes.chroot'
        for source in sorted(includes.rglob('*')):
            if source.is_file() and '__pycache__' not in source.parts and source.suffix not in ('.pyc', '.pyo'):
                relative = str(source.relative_to(includes))
                actual = subprocess.check_output(['unsquashfs', '-cat', '-o', offset, str(iso), relative], stderr=subprocess.PIPE)
                if actual != source.read_bytes():
                    raise ValueError(f'ISO desktop configuration differs from source: {relative}')
        twig = subprocess.check_output(['unsquashfs', '-cat', '-o', offset, str(iso), 'usr/bin/twig'], stderr=subprocess.PIPE)
        if twig != (ROOT / 'vendor/twig/twig.py').read_bytes():
            raise ValueError('ISO Twig runtime differs from the vendored source')
        binary = subprocess.check_output(['unsquashfs','-cat','-o',offset,str(iso),'usr/bin/labwc'],stderr=subprocess.PIPE)
        build = json.loads(subprocess.check_output(['unsquashfs','-cat','-o',offset,str(iso),'usr/share/erdos/labwc-build.json'],stderr=subprocess.PIPE))
        if build.get('sha256') != hashlib.sha256(binary).hexdigest() or build.get('effects') is not False:
            raise ValueError('ISO labwc binary/build verification failed')
        for project in ('labwc','wlroots'):
            checksum=hashlib.sha256()
            for path in sorted((ROOT/'vendor'/project).rglob('*')):
                if path.is_file():
                    checksum.update(str(path.relative_to(ROOT/'vendor'/project)).encode()+b'\0'+path.read_bytes())
            if build.get(project+'_source_sha256') != checksum.hexdigest():
                raise ValueError(f'ISO {project} source provenance differs from current source')
        components=json.loads(subprocess.check_output(['unsquashfs','-cat','-o',offset,str(iso),'usr/share/erdos/components.json'],stderr=subprocess.PIPE))
        if components['labwc_binary_sha256']!=build['sha256']:
            raise ValueError('Component version record does not match installed compositor')
        return packages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iso', type=Path, default=ROOT / 'dist/erdos-amd64.iso')
    parser.add_argument('--verify-only', action='store_true', help='Verify the final image without creating assets or updating metadata')
    parser.add_argument('--version', help='Public release label for an unchanged, already tested ISO')
    parser.add_argument('--date', help='Build date in YYYY-MM-DD form; unchanged images retain their recorded date')
    args = parser.parse_args()
    for tool in ('xorriso', 'unsquashfs'):
        if not shutil.which(tool):
            parser.error(f'Install required tool: {tool}')
    iso = args.iso.resolve(strict=True)
    subprocess.run([sys.executable, str(ROOT / 'scripts/check-project.py')], check=True)
    packages = verify_image(iso)
    if args.verify_only:
        print('PASS: final ISO matches source configuration and retains required installed packages')
        return
    checksum = digest(iso)
    metadata_path = ROOT / 'docs/release.json'
    metadata = json.loads(metadata_path.read_text())
    if args.date:
        date = datetime.date.fromisoformat(args.date).isoformat()
    elif metadata['iso']['sha256'] == checksum:
        date = metadata['date']
    else:
        date = datetime.datetime.fromtimestamp(iso.stat().st_mtime).date().isoformat()
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    canonical = output / 'erdos-amd64.iso'
    if iso != canonical.resolve():
        shutil.copyfile(iso, canonical)
    release_fields = dict(line.split('=', 1) for line in (ROOT / 'config/includes.chroot/etc/erdos-release').read_text().splitlines() if '=' in line)
    version = args.version or release_fields['VERSION']
    if not re.fullmatch(r'[a-zA-Z0-9._-]+', version):
        parser.error('Invalid release version')
    metadata['image_version'] = release_fields['VERSION']
    metadata.update(published=False, tag=None, date=date, status='Prepared image; not published', version=version)
    metadata.pop('download_base_url', None)
    metadata['iso'] = {'filename': canonical.name, 'bytes': canonical.stat().st_size, 'sha256': checksum}
    metadata['source_filename'] = 'erdos-build-project.zip'
    metadata['packages_filename'] = 'erdos-amd64.packages'
    metadata['checksums_filename'] = 'SHA256SUMS'
    metadata_path.write_text(json.dumps(metadata, indent=2) + '\n')
    manifest = output / metadata['packages_filename']
    manifest.write_bytes(packages)
    source_archive = output / metadata['source_filename']
    with zipfile.ZipFile(source_archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in public_files(ROOT):
            archive.write(path, 'erdos/' + str(path.relative_to(ROOT)))
    with zipfile.ZipFile(source_archive) as archive:
        if damaged := archive.testzip():
            raise ValueError(f'Corrupt source archive member: {damaged}')
    iso_sidecar = output / (canonical.name + '.sha256')
    iso_sidecar.write_text(f'{checksum}  {canonical.name}\n')
    source_sidecar = output / (source_archive.name + '.sha256')
    source_sidecar.write_text(f'{digest(source_archive)}  {source_archive.name}\n')
    assets = (canonical, iso_sidecar, manifest, source_archive, source_sidecar)
    (output / 'SHA256SUMS').write_text(''.join(f'{digest(path)}  {path.name}\n' for path in assets))
    print(f'PASS: verified ISO configuration, installer policy, core-package retention and pinned Twig')
    print(f'Prepared {len(assets) + 1} local assets in {output}')
    print('Site remains unpublished. Review/test before uploading; no Git or network publication was performed.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        sys.exit(1)
