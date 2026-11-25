#!/usr/bin/env python3
"""Explicit one-time adoption of checked legacy ErdOS files by signed APT packages."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def adoption_plan(root=Path('/')):
    legacy=json.loads((ROOT/'packaging/legacy-files.json').read_text())
    shared=json.loads((ROOT/'packaging/legacy-shared-files.json').read_text())
    plan=[];conflicts=[]
    for name,accepted in {**legacy,**shared}.items():
        path=root/name
        if not path.exists() and not path.is_symlink():continue
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents) or not path.is_file():
            conflicts.append(name);continue
        if sha(path) not in accepted:conflicts.append(name)
        elif name in legacy:plan.append(name)
    binary=root/'usr/local/bin/labwc'
    if not binary.exists():
        raise ValueError('Only a known labwc-based ErdOS installation can use this migration')
    if binary.exists() or binary.is_symlink():
        record=root/'usr/local/share/doc/labwc/build.json'
        try:
            data=json.loads(record.read_text())
            pin=json.loads((ROOT/'vendor/labwc-fork.json').read_text())
            if (binary.is_symlink() or record.is_symlink()
                    or any(parent.is_symlink() for path in (binary,record) for parent in path.parents)
                    or sha(binary)!=data['sha256']
                    or data['labwc_source_sha256']!=pin['vendor_tree_sha256']):
                raise ValueError('Unsupported compositor')
        except (OSError,ValueError,KeyError):conflicts.append('usr/local/bin/labwc')
        else:plan+=['usr/local/bin/labwc','usr/local/share/doc/labwc/build.json']
    # Refuse unknown files that could shadow or be overwritten by package-owned executables.
    for original in (ROOT/'config/includes.chroot/usr/bin').glob('erdos-*'):
        target=root/'usr/bin'/original.name
        if target.exists() or target.is_symlink():conflicts.append(str(target.relative_to(root)))
    for name in ('labwc','twig'):
        target=root/'usr/bin'/name
        if target.exists() or target.is_symlink():conflicts.append('usr/bin/'+name)
    if conflicts:raise ValueError('Local modifications or unsupported files; nothing changed:\n  '+'\n  '.join(sorted(set(conflicts))))
    return sorted(set(plan))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Configure signed source, install packages interactively, then back up legacy shadows')
    args=parser.parse_args()
    pending=Path('/var/lib/erdos/apt-migration/pending.json')
    if pending.is_symlink():raise ValueError('Refusing symlinked migration state')
    if not pending.exists() and subprocess.run(['dpkg-query','-W','-f=${Status}','erdos-desktop'],capture_output=True,text=True).stdout=='install ok installed':
        print('Already package-managed. Use sudo apt update and sudo apt upgrade.');return
    if pending.exists():
        previous_hashes=json.loads(pending.read_text())
        if not isinstance(previous_hashes,dict) or any(not name.startswith('usr/local/') or '..' in Path(name).parts for name in previous_hashes):
            raise ValueError('Invalid pending migration state')
        plan=sorted(previous_hashes)
        for name in plan:
            path=Path('/')/name
            if path.is_symlink() or not path.is_file() or sha(path)!=previous_hashes[name]:
                raise ValueError('Pending legacy file was modified; retained: '+name)
        print('Resuming a previously checked migration.')
    else:
        plan=adoption_plan()
        previous_hashes={name:sha(Path('/')/name) for name in plan}
    print('Checked legacy files to archive after successful package installation:')
    for name in plan:print('  /'+name)
    print('Homes, drivers, firmware, DKMS, bootloader, power and network configurations are not migrated.')
    if not args.apply:
        print('Dry run only. Review, then run with sudo and --apply.');return
    if os.geteuid()!=0:parser.error('--apply requires sudo')
    policy=json.loads((ROOT/'packaging/repository.json').read_text())
    key=ROOT/policy['public_key']
    if sha(key)!=policy['public_key_sha256']:raise ValueError('Public key differs from the pinned source')
    print('Pinned archive key:',policy['fingerprint'])
    for relative in ['usr/share/keyrings/erdos-archive-keyring.asc','etc/apt/sources.list.d/erdos-updates.sources','etc/apt/preferences.d/erdos-updates']:
        source=ROOT/'config/includes.chroot'/relative;destination=Path('/')/relative
        if destination.is_symlink():raise ValueError('Refusing symlinked repository configuration')
        if destination.exists() and destination.read_bytes()!=source.read_bytes():raise ValueError('Existing repository configuration differs: '+str(destination))
    for relative in ['usr/share/keyrings/erdos-archive-keyring.asc','etc/apt/sources.list.d/erdos-updates.sources','etc/apt/preferences.d/erdos-updates']:
        source=ROOT/'config/includes.chroot'/relative;destination=Path('/')/relative
        destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination);destination.chmod(0o644)
    if not pending.exists():
        pending.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        temporary=pending.with_suffix('.tmp')
        temporary.write_text(json.dumps(previous_hashes,indent=2)+'\n');temporary.chmod(0o600)
        temporary.replace(pending)
    subprocess.run(['apt-get','--error-on=any','update'],check=True)
    subprocess.run(['apt-get','--no-remove','install','erdos-desktop'],check=True)
    # Recheck local edits that may have happened while APT/authentication was open.
    # New /usr files now belong to packages, so only legacy shadows are checked here.
    for name in plan:
        path=Path('/')/name
        if path.is_symlink() or sha(path)!=previous_hashes[name]:raise ValueError('Legacy file changed during installation; retained: '+str(path))
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=Path('/var/lib/erdos/apt-migration')/stamp;backup.mkdir(parents=True,mode=0o700)
    moved=[];links={}
    try:
        for name in plan:
            source=Path('/')/name;destination=backup/name;destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.move(str(source),str(destination));moved.append(name)
        # Existing menus/startup commands may use absolute /usr/local paths.
        # Administrative compatibility links follow package updates without
        # rewriting user files or retaining stale executable copies.
        commands={path.name for path in (ROOT/'config/includes.chroot/usr/bin').glob('erdos-*')}|{'labwc','twig'}
        for name in plan:
            target=Path('/usr/bin')/Path(name).name
            if name.startswith('usr/local/bin/') and target.name in commands and target.is_file():
                (Path('/')/name).symlink_to(target);links[name]=str(target)
        (backup/'manifest.json').write_text(json.dumps({'schema':1,'files':plan,'compatibility_links':links},indent=2)+'\n')
    except BaseException:
        for name in links:(Path('/')/name).unlink()
        for name in reversed(moved):
            destination=Path('/')/name;destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.move(str(backup/name),str(destination))
        raise
    pending.unlink()
    print('Legacy desktop backed up at:',backup)
    print('Log out and back in. Future ErdOS updates use normal APT upgrades.')

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,subprocess.SubprocessError) as error:raise SystemExit(str(error))
