#!/usr/bin/env python3
"""Source-only checks: syntax, local documentation links and installer safety."""
import ast
import datetime
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

from project_files import public_files

ROOT = Path(__file__).resolve().parent.parent


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.ids = set()
        self.links = []
        self.feed(path.read_text())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            if attrs['id'] in self.ids:
                raise ValueError(f'{self.path.name}: duplicate id {attrs["id"]}')
            self.ids.add(attrs['id'])
        if tag == 'img' and 'alt' not in attrs:
            raise ValueError(f'{self.path.name}: image needs alternative text')
        for key in ('href', 'src', 'data-image'):
            if attrs.get(key):
                self.links.append(attrs[key])


def check_link(path, value, pages, *, website=False):
    url = urlsplit(value)
    if url.scheme or url.netloc:
        if url.scheme not in {'', 'https', 'http', 'mailto'}:
            raise ValueError(f'{path}: unsupported link scheme: {value}')
        return
    if website and url.path.startswith('/'):
        raise ValueError(f'{path}: use relative links for project Pages: {value}')
    target = (path.parent / unquote(url.path)).resolve() if url.path else path.resolve()
    if target.is_dir():
        target /= 'index.html'
    if not target.is_relative_to(ROOT) or not target.is_file():
        raise ValueError(f'{path.relative_to(ROOT)}: broken local link: {value}')
    if website and not target.is_relative_to(ROOT / 'docs'):
        raise ValueError(f'{path}: site asset escapes docs/: {value}')
    if url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
        raise ValueError(f'{path.relative_to(ROOT)}: missing fragment: {value}')


def main():
    files = list(public_files(ROOT))
    if (ROOT / '.git').exists():
        listed = subprocess.check_output(['git', '-c', f'safe.directory={ROOT}', '-C', str(ROOT), 'ls-files', '--cached', '--others', '--exclude-standard', '-z'])
        # Tracked deletions are no longer part of the working-tree source archive.
        candidates = {name.decode() for name in listed.split(b'\0') if name and (ROOT / name.decode()).exists()}
        expected = {str(path.relative_to(ROOT)) for path in files}
        if candidates != expected:
            raise ValueError(f'Git/source archive boundary differs: unexpected={sorted(candidates - expected)}, missing={sorted(expected - candidates)}')
    pages = {p.resolve(): Page(p) for p in files if p.suffix == '.html'}
    for path in files:
        relative = path.relative_to(ROOT)
        if path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError(f'Large generated file in public source: {relative}')
        if path.name == '.env' or path.name.startswith('.env.') or path.suffix in {'.iso', '.qcow2', '.zip', '.img', '.raw', '.vmdk', '.vdi', '.bin', '.c32', '.log', '.pem', '.key'}:
            raise ValueError(f'Private/generated file in public source: {relative}')
        if path.suffix == '.py' or path.read_bytes().startswith(b'#!/usr/bin/env python3'):
            ast.parse(path.read_text(), filename=str(relative))
        if path.suffix == '.xml':
            ET.parse(path)
        if path.suffix in {'.sh', '.chroot', '.binary'} or path.name in {'autostart', '.profile'} or path.read_bytes().startswith(b'#!/bin/sh'):
            # Package lists are .chroot files too; only shell sources are parsed.
            first = path.read_bytes().splitlines()[0] if path.stat().st_size else b''
            if path.suffix == '.sh' or first.startswith(b'#!') or path.name == '.profile':
                shell = 'sh' if first == b'#!/bin/sh' else 'bash'
                subprocess.run([shell, '-n', str(path)], check=True)
        if path.suffix == '.html':
            for value in pages[path.resolve()].links:
                check_link(path, value, pages, website=True)
        if path.suffix == '.md':
            for value in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)\)', path.read_text()):
                check_link(path, value, pages)
        if path.suffix in {'.md', '.py', '.sh', '.yml', '.yaml', '.json', '.html'}:
            text = path.read_text()
            if re.search(r'-----BEGIN (?:(?:RSA |EC |OPENSSH )?PRIVATE KEY|PGP PRIVATE KEY BLOCK)-----', text):
                raise ValueError(f'Private key in public source: {relative}')

    # The maintained fork is the source of compositor changes. Check its pin
    # offline so ordinary builds need neither another clone nor network access.
    fork = json.loads((ROOT / 'vendor/labwc-fork.json').read_text())
    if fork.get('schema') != 1:
        raise ValueError('Invalid labwc fork pin schema')
    for field in ('fork_commit', 'upstream_commit'):
        if not re.fullmatch(r'[a-f0-9]{40}', fork[field]):
            raise ValueError(f'Invalid labwc fork pin: {field}')
    note = dict(line.split(': ', 1) for line in (ROOT / 'vendor/labwc/UPSTREAM').read_text().splitlines()
                if ': ' in line)
    if note['Commit'] != fork['upstream_commit'] or note['Version'] != fork['upstream_version']:
        raise ValueError('labwc UPSTREAM note differs from the recorded fork base')
    digest = hashlib.sha256()
    source = ROOT / 'vendor/labwc'
    for path in sorted(source.rglob('*')):
        if path.is_file():
            digest.update(str(path.relative_to(source)).encode() + b'\0' + path.read_bytes())
    if digest.hexdigest() != fork['vendor_tree_sha256']:
        raise ValueError('Vendored labwc differs from its fork pin; see docs/upstream-labwc.md')

    preseed = ROOT / 'config/includes.installer/preseed.cfg'
    settings = {}
    for line in preseed.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        parts = line.split(None, 3)
        key = parts[1]
        if key in settings:
            raise ValueError(f'Duplicate installer setting: {key}')
        settings[key] = parts[3] if len(parts) == 4 else ''
        if key.startswith('partman') or key == 'grub-installer/bootdev' or key.startswith('passwd/user-') or key.startswith('passwd/root-password'):
            raise ValueError(f'Keep disk choices and account credentials interactive: {key}')
    if settings.get('passwd/root-login') != 'false' or settings.get('passwd/make-user') != 'true':
        raise ValueError('First-account sudo requires disabled root login and user creation')

    repository = json.loads((ROOT / 'packaging/repository.json').read_text())
    key = (ROOT / repository['public_key']).resolve()
    if not key.is_relative_to(ROOT) or not key.read_bytes().startswith(b'-----BEGIN PGP PUBLIC KEY BLOCK-----'):
        raise ValueError('Archive key must be a public key inside the source boundary')
    if hashlib.sha256(key.read_bytes()).hexdigest() != repository['public_key_sha256']:
        raise ValueError('Archive public key differs from its pinned digest')
    if not re.fullmatch(r'[A-F0-9]{40}', repository['fingerprint']):
        raise ValueError('Invalid archive key fingerprint')
    release = json.loads((ROOT / 'docs/release.json').read_text())
    if release.get('schema') != 1 or not re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+', release['repository']):
        raise ValueError('Invalid release schema or repository')
    datetime.date.fromisoformat(release['date'])
    if type(release['published']) is not bool:
        raise ValueError('published must be a boolean')
    if release['published'] and not isinstance(release['tag'], str):
        raise ValueError('A published release needs its real tag')
    if release['published'] and not release['tag'].strip():
        raise ValueError('A published release needs a nonempty tag')
    if not re.fullmatch(r'[a-f0-9]{64}', release['iso']['sha256']) or type(release['iso']['bytes']) is not int or release['iso']['bytes'] <= 0:
        raise ValueError('Invalid ISO checksum or size')
    for name in (release['iso']['filename'], release['source_filename'], release['packages_filename'], release['checksums_filename']):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or name in {'.', '..'}:
            raise ValueError(f'Invalid release asset filename: {name}')
    print(f'PASS: {len(files)} public source files; syntax, local links, installer policy and release metadata')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, SyntaxError, ET.ParseError, subprocess.CalledProcessError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        sys.exit(1)
