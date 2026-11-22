#!/usr/bin/env python3
"""Prepare a small, versioned desktop update; never include machine configuration."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'config/includes.chroot'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version', help='Unique immutable update ID, for example 2026.11.22-settings.1')
    parser.add_argument('--sequence', required=True, type=int, help='Strictly increasing publication number')
    parser.add_argument('--baseline', default='28356b2949948409509fe82d1935d04b06850102', help='Known previous source revision')
    parser.add_argument('--previous', type=Path, action='append', default=[], help='Previously published desktop.json.gz; retains accepted file checksums')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/updates')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9._-]+', args.version) or args.sequence < 1:
        parser.error('Invalid version or sequence')
    previous = {}
    for path in args.previous:
        data = json.loads(gzip.decompress(path.read_bytes()))
        if args.sequence <= data['sequence']:
            parser.error('Sequence must be newer than every previous bundle')
        for item in data['files']:
            previous.setdefault(item['path'], set()).update([item['sha256'], *item['previous']])
    paths = [*sorted([*(SOURCE / 'usr/local/bin').glob('erdos-*'), ROOT / 'scripts/erdos-update.py'], key=lambda p: 'erdos-update' if p.name == 'erdos-update.py' else p.name),
             *sorted((SOURCE / 'usr/local/lib/erdos').glob('*.py')),
             SOURCE / 'etc/erdos-release',
             SOURCE / 'usr/share/applications/erdos-settings.desktop',
             SOURCE / 'usr/share/xdg-desktop-portal/labwc-portals.conf',
             SOURCE / 'usr/lib/systemd/user/erdos-background.service']
    files = []
    for path in paths:
        name = 'usr/local/bin/erdos-update' if path == ROOT / 'scripts/erdos-update.py' else str(path.relative_to(SOURCE))
        content = path.read_bytes()
        accepted = previous.get(name, set()).copy()
        baseline = subprocess.run(['git', 'show', f'{args.baseline}:config/includes.chroot/{name}'],
                                  cwd=ROOT, capture_output=True)
        if baseline.returncode == 0:
            accepted.add(sha(baseline.stdout))
        files.append({'path': name, 'mode': 0o755 if path.stat().st_mode & 0o111 else 0o644,
                      'sha256': sha(content), 'previous': sorted(accepted),
                      'data': base64.b64encode(content).decode()})
    data = {'schema': 1, 'version': args.version, 'sequence': args.sequence,
            'labwc_sha256': sha((ROOT / 'release-tools/labwc').read_bytes()), 'files': files}
    raw = gzip.compress(json.dumps(data, sort_keys=True, separators=(',', ':')).encode(), mtime=0)
    output = args.output / args.version / 'desktop.json.gz'
    if output.exists() and output.read_bytes() != raw:
        parser.error('An immutable update ID cannot be reused with different contents')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    (args.output / 'latest.json').write_text(json.dumps({'schema': 1, 'version': args.version,
                                                       'sha256': sha(raw)}, indent=2) + '\n')
    (args.output / 'erdos-update.py').write_bytes((ROOT / 'scripts/erdos-update.py').read_bytes())
    (args.output / 'update.sh').write_bytes((ROOT / 'scripts/update.sh').read_bytes())
    print(f'Prepared {len(files)} desktop files, {len(raw):,} compressed bytes: {output}')


if __name__ == '__main__':
    main()
