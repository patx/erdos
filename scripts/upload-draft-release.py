#!/usr/bin/env python3
"""Upload verified build assets to a draft prerelease; never publish it.

Requires GitHub CLI and GH_TOKEN with contents:write for the chosen repository.
The token stays in the environment, not command arguments or build containers.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time


ASSETS = ('erdos-amd64.iso', 'erdos-amd64.iso.sha256', 'erdos-amd64.packages',
          'erdos-build-project.zip', 'erdos-build-project.zip.sha256',
          'erdos-build.json', 'SHA256SUMS')


def run(*args):
    return subprocess.check_output(args, text=True)


def api(path):
    return json.loads(run('gh', 'api', path))


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def draft(repository, tag):
    releases = api(f'repos/{repository}/releases?per_page=100')
    release = next((r for r in releases if r['tag_name'] == tag), None)
    if release and not release['draft']:
        raise ValueError('Refusing to change a published release')
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--notes', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repository):
        parser.error('Invalid repository')
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?', args.tag):
        parser.error('Use a version tag, such as v1.0.0-alpha.2')
    root = args.directory.resolve(strict=True)
    commit = run('git', '-C', str(root), 'rev-parse', 'HEAD').strip()
    remote_commit = api(f'repos/{args.repository}/commits/{args.tag}')['sha']
    if remote_commit != commit:
        raise ValueError('Build checkout does not match the remote release tag')
    release = draft(args.repository, args.tag)
    if args.check_only:
        print('PASS: tag matches checkout; destination is missing or still a draft')
        return
    if not args.notes or not args.notes.is_file():
        parser.error('Upload requires --notes pointing to a build-specific notes file')
    paths = {name: root / 'dist' / name for name in ASSETS}
    expected = {name: (checksum(path), path.stat().st_size) for name, path in paths.items()}
    metadata = json.loads((root / 'docs/release.json').read_text())
    if (metadata['iso']['sha256'], metadata['iso']['bytes']) != expected['erdos-amd64.iso']:
        raise ValueError('Prepared ISO differs from release metadata')
    entries = {}
    for line in paths['SHA256SUMS'].read_text().splitlines():
        digest, name = line.split('  ', 1)
        if name in entries:
            raise ValueError('Duplicate checksum entry')
        entries[name] = digest
    if entries != {n: v[0] for n, v in expected.items() if n != 'SHA256SUMS'}:
        raise ValueError('SHA256SUMS must match every other uploaded asset')
    record = json.loads(paths['erdos-build.json'].read_text())
    if record['source_commit'] != commit or record['source_tag'] != args.tag:
        raise ValueError('Build record does not match the source tag')
    if record['iso'] != metadata['iso']:
        raise ValueError('Build record does not match the prepared ISO')
    if release is None:
        subprocess.run(['gh', 'release', 'create', args.tag, '--repo', args.repository,
                        '--draft', '--prerelease', '--verify-tag', '--title', 'ErdOS ' + args.tag.removeprefix('v'),
                        '--notes-file', str(args.notes.resolve())], check=True)
        release = draft(args.repository, args.tag)
    if release is None:
        raise ValueError('Draft release was not found after creation; retry later')
    subprocess.run(['gh', 'release', 'edit', args.tag, '--repo', args.repository,
                    '--draft=true', '--prerelease=true', '--notes-file', str(args.notes.resolve())], check=True)

    def matches(name):
        assets = api(f'repos/{args.repository}/releases/{release["id"]}/assets?per_page=100')
        a = next((a for a in assets if a['name'] == name), None)
        digest, size = expected[name]
        return a is not None and a['state'] == 'uploaded' and a['size'] == size and a.get('digest') == 'sha256:' + digest

    for name, path in paths.items():
        for attempt in range(3):
            current = draft(args.repository, args.tag)
            if current is None or current['id'] != release['id']:
                raise ValueError('Draft destination changed during upload')
            if matches(name):
                break
            result = subprocess.run(['gh', 'release', 'upload', args.tag, str(path),
                                     '--repo', args.repository, '--clobber'])
            # A disconnected response may follow a successful server-side upload.
            if matches(name):
                break
            if attempt == 2:
                raise ValueError(f'Upload or server SHA-256 verification failed: {name} (exit {result.returncode})')
            time.sleep(2)
        print('Uploaded and server SHA-256 verified:', name, flush=True)
    if not all(matches(name) for name in paths):
        raise ValueError('Release assets changed during final verification')
    if draft(args.repository, args.tag) is None:
        raise ValueError('Draft disappeared after verification')
    print('PASS: all seven assets verified; release remains an unpublished draft')
    print(release['html_url'])


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        sys.exit(1)
