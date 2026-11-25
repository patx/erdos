#!/usr/bin/env python3
"""Package existing ErdOS components; no compiler or signing key enters the image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tarfile
from project_files import public_files
ROOT=Path(__file__).resolve().parents[1]
INCLUDES=ROOT/'config/includes.chroot'

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def copy(source, root, relative):
    destination=root/relative;destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,destination)
    destination.chmod(0o755 if source.stat().st_mode&0o111 else 0o644)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    inputs=parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--labwc-dir',type=Path)
    inputs.add_argument('--reuse-compositor',type=Path,help='Repackage unchanged verified compositor bytes with current desktop helpers')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--version')
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='erdos-compositor-reuse-') as directory:
        args.reused_dependencies=None
        if args.reuse_compositor:
            name=subprocess.check_output(['dpkg-deb','-f',str(args.reuse_compositor),'Package'],text=True).strip()
            if name!='erdos-labwc':raise ValueError('Expected an erdos-labwc package')
            extracted=Path(directory)
            subprocess.run(['dpkg-deb','-x',str(args.reuse_compositor),str(extracted)],check=True)
            args.labwc_dir=extracted/'usr/bin'
            shutil.copyfile(extracted/'usr/share/erdos/labwc-build.json',args.labwc_dir/'labwc.build.json')
            args.reused_dependencies=subprocess.check_output(['dpkg-deb','-f',str(args.reuse_compositor),'Depends'],text=True).strip()
        build(args)


def build(args):
    versions=json.loads((ROOT/'packaging/versions.json').read_text())
    version=args.version or versions['package_version']
    subprocess.run(['dpkg','--validate-version',version],check=True)
    record=json.loads((args.labwc_dir/'labwc.build.json').read_text())
    if record.get('prefix')!='/usr' or sha(args.labwc_dir/'labwc')!=record['sha256']:
        raise ValueError('Use a verified /usr-prefix compositor build')
    for name in ('labwc','wlroots'):
        if record[name]!=versions[name]:raise ValueError('Compositor version does not match package metadata')
        digest=hashlib.sha256()
        for path in sorted((ROOT/'vendor'/name).rglob('*')):
            if path.is_file():digest.update(str(path.relative_to(ROOT/'vendor'/name)).encode()+b'\0'+path.read_bytes())
        if digest.hexdigest()!=record[name+'_source_sha256']:raise ValueError('Compositor source differs from this checkout')
    args.output.mkdir(parents=True,exist_ok=True)
    files=list(public_files(ROOT));digest=hashlib.sha256()
    for path in files:digest.update(str(path.relative_to(ROOT)).encode()+b'\0'+path.read_bytes())
    source_revision='source archive'
    if shutil.which('git') and (ROOT/'.git').exists():
        revision=subprocess.run(['git','-c',f'safe.directory={ROOT}','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True)
        status=subprocess.run(['git','-c',f'safe.directory={ROOT}','status','--porcelain'],cwd=ROOT,capture_output=True,text=True)
        if revision.returncode==0:source_revision=revision.stdout.strip()+('+dirty' if status.stdout else '')
    metadata={**versions,'package_version':version,'source_revision':source_revision,'source_sha256':digest.hexdigest(),'labwc_binary_sha256':record['sha256']}
    dependencies={
        'erdos-desktop':f'erdos-labwc (= {version}), erdos-archive-keyring, python3, python3-gi, gir1.2-gtk-3.0, gir1.2-gtksource-4, gsettings-desktop-schemas, dconf-gsettings-backend, dbus-user-session, wlr-randr, swaybg, grim, slurp, network-manager, bluez, pipewire-bin, wireplumber, sudo, desktop-file-utils',
        'erdos-labwc':'libc6 (>= 2.41), libwayland-server0, libwayland-client0, libinput10, libseat1, libdrm2, libgbm1, libegl1, libgles2, libpixman-1-0, libdisplay-info2, libliftoff0, libudev1, libxkbcommon0, libcairo2, libpango-1.0-0, libpangocairo-1.0-0, libxml2, libglib2.0-0t64, libsfdo0, libxcb-ewmh2, libxcb-icccm4, libxcb-dri3-0, libxcb-present0, libxcb-render0, libxcb-xfixes0, libxcb-composite0, libxcb-res0, libxcb-errors0, libpng16-16t64, librsvg2-2, xwayland',
        'erdos-archive-keyring':'apt (>= 2.6), ca-certificates',
    }
    with tempfile.TemporaryDirectory(prefix='erdos-debs-') as temporary:
        temporary=Path(temporary)
        if args.reused_dependencies:
            dependencies['erdos-labwc']=args.reused_dependencies
        else:
            scan=temporary/'scan';(scan/'debian').mkdir(parents=True)
            (scan/'debian/control').write_text('Source: erdos-components\n\nPackage: erdos-labwc\nArchitecture: amd64\n')
            result=subprocess.check_output(['dpkg-shlibdeps','-O','-e'+str((args.labwc_dir/'labwc').resolve())],cwd=scan,text=True)
            dependencies['erdos-labwc']=next(line.split('=',1)[1] for line in result.splitlines() if line.startswith('shlibs:Depends='))+', xwayland'
        roots={name:temporary/name for name in dependencies}
        for root in roots.values():root.mkdir()
        desktop=roots['erdos-desktop'];keyring=roots['erdos-archive-keyring'];compositor=roots['erdos-labwc']
        for path in sorted(INCLUDES.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts:continue
            relative=path.relative_to(INCLUDES);name=str(relative)
            if name in ('usr/share/keyrings/erdos-archive-keyring.asc','etc/apt/sources.list.d/erdos-updates.sources','etc/apt/preferences.d/erdos-updates'):
                copy(path,keyring,relative)
            elif name.startswith(('usr/bin/erdos-','usr/lib/erdos/','usr/lib/systemd/user/erdos-','usr/lib/live/config/9990-erdos-','usr/lib/udev/rules.d/91-erdos-','usr/share/erdos/','usr/share/themes/ErdOS/','usr/share/applications/erdos-','etc/skel/.config/','etc/erdos/')):
                copy(path,desktop,relative)
        subprocess.run(['sh',str(ROOT/'scripts/stage-twig.sh'),str(desktop)],check=True)
        # Component versions change on package updates; image identity remains in /etc.
        dest=desktop/'usr/share/erdos/components.json';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(metadata,indent=2)+'\n')
        copy(args.labwc_dir/'labwc',compositor,'usr/bin/labwc')
        copy(args.labwc_dir/'labwc.build.json',compositor,'usr/share/erdos/labwc-build.json')
        for name in ('labwc','wlroots'):
            copy(ROOT/'vendor'/name/'UPSTREAM',compositor,f'usr/share/erdos/provenance/{name}')
        for name,root in roots.items():
            doc=root/'usr/share/doc'/name;doc.mkdir(parents=True,exist_ok=True)
            license_text=(ROOT/'LICENSE').read_text() if name!='erdos-labwc' else '\n\n'.join((ROOT/'vendor'/p/'LICENSE').read_text() for p in ('labwc','wlroots'))
            (doc/'copyright').write_text(license_text)
            control=root/'DEBIAN';control.mkdir()
            extra='Provides: labwc\nConflicts: labwc\nReplaces: labwc\n' if name=='erdos-labwc' else ''
            size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
            (control/'control').write_text(f'Package: {name}\nSource: erdos-components\nVersion: {version}\nArchitecture: '+('amd64' if name=='erdos-labwc' else 'all')+f'\nMaintainer: ErdOS maintainers <noreply@erd.sh>\nSection: x11\nPriority: optional\nInstalled-Size: {(size+1023)//1024}\nDepends: {dependencies[name]}\n{extra}Description: ErdOS '+{'erdos-desktop':'desktop helpers, Settings, Twig and session defaults','erdos-labwc':'pinned labwc compositor with native ErdOS integration','erdos-archive-keyring':'scoped archive key and APT source'}[name]+'\n')
            conffiles=['/'+str(p.relative_to(root)) for p in (root/'etc').rglob('*') if p.is_file()] if (root/'etc').exists() else []
            if conffiles:(control/'conffiles').write_text('\n'.join(conffiles)+'\n')
            archive=args.output/f'{name}_{version}_{"amd64" if name=="erdos-labwc" else "all"}.deb'
            subprocess.run(['dpkg-deb','--root-owner-group','-Zxz','--build',str(root),str(archive)],check=True)
    # Preserve the exact public source snapshot identified by this package.
    with tarfile.open(args.output/'erdos-components-source.tar.gz','w:gz') as archive:
        for path in files:archive.add(path,arcname=str(path.relative_to(ROOT)),recursive=False)
    (args.output/'components.json').write_text(json.dumps(metadata,indent=2)+'\n')

if __name__=='__main__':main()
