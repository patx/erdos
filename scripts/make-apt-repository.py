#!/usr/bin/env python3
"""Build a signed static APT archive; publish InRelease only after immutable files."""
import argparse
import datetime
import email.utils
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import tarfile
from project_files import public_files
ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packages',type=Path,default=ROOT/'dist/packages')
    parser.add_argument('--output',type=Path,default=ROOT/'dist/apt')
    parser.add_argument('--gnupg-home',type=Path,required=True)
    parser.add_argument('--signing-key',required=True)
    parser.add_argument('--refresh',action='store_true',help='Refresh only signed metadata of an existing archive; keep package/source bytes immutable')
    args=parser.parse_args()
    policy=json.loads((ROOT/'packaging/repository.json').read_text())
    if args.signing_key!=policy['fingerprint']:parser.error('Signing key differs from the pinned public key')
    keys=subprocess.check_output(['gpg','--homedir',str(args.gnupg_home),'--with-colons','--show-keys',str(ROOT/policy['public_key'])],text=True)
    if not any(line.startswith('fpr:') and line.split(':')[9]==policy['fingerprint'] for line in keys.splitlines()):
        raise ValueError('Pinned fingerprint does not match the distributed public key')
    def gpg(*command):
        subprocess.run(['gpg','--homedir',str(args.gnupg_home),'--batch','--yes','--local-user',args.signing_key,'--digest-algo','SHA256',*command],check=True)
    if args.refresh:
        distribution=args.output/'dists'/policy['suite']
        gpg('--verify',str(distribution/'InRelease'))
        now=datetime.datetime.now(datetime.timezone.utc)
        text=(distribution/'Release').read_text()
        lines=[line for line in text.splitlines() if not line.startswith(('Date:','Valid-Until:'))]
        lines.insert(0,'Date: '+email.utils.format_datetime(now,usegmt=True))
        lines.insert(1,'Valid-Until: '+email.utils.format_datetime(now+datetime.timedelta(days=policy['valid_days']),usegmt=True))
        with tempfile.TemporaryDirectory(prefix='erdos-resign-',dir=args.output.parent) as directory:
            staged=Path(directory)/'Release';staged.write_text('\n'.join(lines)+'\n')
            gpg('--armor','--detach-sign','--output',str(staged.with_name('Release.gpg')),str(staged))
            gpg('--clearsign','--output',str(staged.with_name('InRelease')),str(staged))
            for name in ('Release','Release.gpg','InRelease'):shutil.copyfile(staged.with_name(name),distribution/name)
        manifest=json.loads((args.output/'publication.json').read_text())
        for name in manifest['files']:manifest['files'][name]=sha(args.output/name)
        (args.output/'publication.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print('Refreshed signed metadata without changing packages or sources');return
    metadata=json.loads((args.packages/'components.json').read_text());version=metadata['package_version']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists():raise ValueError('Choose a new output directory; never overwrite an existing signed archive')
    with tempfile.TemporaryDirectory(prefix='erdos-apt-',dir=args.output.parent) as temporary:
        temporary=Path(temporary);archive=temporary/'archive';pool=archive/'pool/main/e/erdos-components';pool.mkdir(parents=True)
        packages=sorted(args.packages.glob('*.deb'))
        expected={'erdos-desktop','erdos-labwc','erdos-archive-keyring'}
        found=set()
        for package in packages:
            name=subprocess.check_output(['dpkg-deb','-f',str(package),'Package'],text=True).strip()
            found.add(name)
            current=subprocess.check_output(['dpkg-deb','-f',str(package),'Version'],text=True).strip()
            if name not in expected or current!=version:raise ValueError('Unexpected component package or version')
            shutil.copyfile(package,pool/package.name)
        if found!=expected or len(packages)!=3:raise ValueError('Expected exactly the three component packages')
        snapshot=temporary/'snapshot';snapshot.mkdir()
        bundle=args.packages/'erdos-components-source.tar.gz'
        if bundle.exists():
            with tarfile.open(bundle) as snapshot_archive:
                for member in snapshot_archive.getmembers():
                    if not member.isfile() or Path(member.name).is_absolute() or '..' in Path(member.name).parts:
                        raise ValueError('Unsafe source snapshot entry')
                snapshot_archive.extractall(snapshot,filter='data')
        else:
            for path in public_files(ROOT):
                target=snapshot/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        digest=hashlib.sha256()
        for path in public_files(snapshot):digest.update(str(path.relative_to(snapshot)).encode()+b'\0'+path.read_bytes())
        if digest.hexdigest()!=metadata['source_sha256']:raise ValueError('Corresponding source differs from packaged source digest')
        source=temporary/f'erdos-components-{version}';shutil.copytree(snapshot,source)
        shutil.copytree(source/'packaging/debian',source/'debian')
        deps=', '.join(dict.fromkeys(['dpkg-dev',*(ROOT/'scripts/build-dependencies.txt').read_text().split()]))
        (source/'debian/control').write_text(f'Source: erdos-components\nSection: x11\nPriority: optional\nMaintainer: ErdOS maintainers <noreply@erd.sh>\nBuild-Depends: {deps}\nStandards-Version: 4.7.0\nRules-Requires-Root: no\n\n'+''.join(f'Package: {name}\nArchitecture: {"amd64" if name=="erdos-labwc" else "all"}\nDescription: ErdOS custom desktop component\n\n' for name in sorted(expected)))
        date=email.utils.format_datetime(datetime.datetime.now(datetime.timezone.utc))
        (source/'debian/changelog').write_text(f'erdos-components ({version}) unstable; urgency=medium\n\n  * Package the pinned ErdOS components for signed APT delivery.\n\n -- ErdOS maintainers <noreply@erd.sh>  {date}\n')
        subprocess.run(['dpkg-source','--build',str(source)],cwd=temporary,check=True)
        for path in temporary.glob('erdos-components_*'):
            if path.is_file():shutil.copyfile(path,pool/path.name)
        suite=policy['suite'];distribution=archive/'dists'/suite
        indexes=[]
        for directory,kind in [('main/binary-amd64','packages'),('main/source','sources')]:
            target=distribution/directory;target.mkdir(parents=True)
            name='Packages' if kind=='packages' else 'Sources'
            data=subprocess.check_output(['apt-ftparchive',kind,'pool/main/e/erdos-components'],cwd=archive)
            for filename,content in [(name,data),(name+'.gz',gzip.compress(data,mtime=0))]:
                path=target/filename;path.write_bytes(content);indexes.append(path)
                hashed=target/'by-hash/SHA256'/sha(path);hashed.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,hashed)
        now=datetime.datetime.now(datetime.timezone.utc)
        release=distribution/'Release'
        release.write_text('Origin: ErdOS\nLabel: ErdOS\nSuite: '+suite+'\nCodename: '+suite+'\nArchitectures: amd64\nComponents: main\nAcquire-By-Hash: yes\nDate: '+email.utils.format_datetime(now,usegmt=True)+'\nValid-Until: '+email.utils.format_datetime(now+datetime.timedelta(days=policy['valid_days']),usegmt=True)+'\nDescription: ErdOS custom desktop components\nSHA256:\n'+''.join(f' {sha(p)} {p.stat().st_size} {p.relative_to(distribution)}\n' for p in indexes))
        gpg('--armor','--detach-sign','--output',str(distribution/'Release.gpg'),str(release))
        gpg('--clearsign','--output',str(distribution/'InRelease'),str(release))
        gpg('--verify',str(distribution/'InRelease'))
        public=archive/'erdos-archive-keyring.asc';shutil.copyfile(ROOT/policy['public_key'],public)
        manifest={str(p.relative_to(archive)):sha(p) for p in sorted(archive.rglob('*')) if p.is_file()}
        (archive/'publication.json').write_text(json.dumps({'schema':1,'package_version':version,'fingerprint':policy['fingerprint'],'files':manifest},indent=2)+'\n')
        shutil.move(str(archive),str(args.output))
    print('Signed APT archive: '+str(args.output))

if __name__=='__main__':main()
