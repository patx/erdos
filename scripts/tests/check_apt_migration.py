#!/usr/bin/env python3
"""Verify public APT adoption against Beta 1 in a disposable root chroot.

Run through run-in-debian.sh with python3, ca-certificates,
xorriso and squashfs-tools installed in that container. Downloads a verified
1.1 GiB baseline; the managed wrapper removes it and the extracted filesystem.
No host packages or user configuration are changed.
"""
import hashlib,json,os,re,select,shutil,subprocess,time,urllib.request
from pathlib import Path
import sys
PROJECT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROJECT/'scripts'))
from project_files import public_files
import argparse
argparse.ArgumentParser(description=__doc__).parse_args()
if os.geteuid()!=0 or not os.environ.get('ERDOS_TEST_DIR'):
 raise SystemExit('Use scripts/run-in-debian.sh; never run this against your host root.')
work=Path(os.environ['ERDOS_TEST_DIR']);iso=work/'beta1.iso';h=hashlib.sha256()
if iso.exists() or (work/'target').exists():raise SystemExit('Use a new managed test workspace')
with urllib.request.urlopen('https://downloads.erd.sh/v1.0.0-beta.1/erdos-amd64.iso',timeout=90) as response,iso.open('wb') as out:
 while data:=response.read(1024*1024):out.write(data);h.update(data)
assert h.hexdigest()=='128fb9324f41a6934a9ab4751c970144ebba67bfe97dc8ad2fb043fe0b1f4efa'
r=subprocess.run(['xorriso','-indev',str(iso),'-find','/live/filesystem.squashfs','-exec','report_lba','--'],capture_output=True,text=True,check=True)
offset=str(int(re.search(r'File data lba:\s*\d+\s*,\s*(\d+)\s*,',r.stdout+r.stderr)[1])*2048)
root=work/'target';subprocess.run(['unsquashfs','-no-progress','-d',str(root),'-o',offset,str(iso)],check=True,stdout=subprocess.DEVNULL)
resolver=root/'etc/resolv.conf';resolver.unlink(missing_ok=True);resolver.write_text(Path('/etc/resolv.conf').read_text())
source=root/'opt/erdos-source';source.mkdir(parents=True)
for path in public_files(PROJECT):
 dest=source/path.relative_to(PROJECT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
for path in (root/'etc/apt/sources.list.d').iterdir():path.unlink()
(root/'etc/apt/sources.list').write_text('')
(root/'etc/apt/apt.conf.d/99test-no-pty').write_text('Dpkg::Use-Pty "0";\n')
protected={}
for name,value in [('home/tester/.config/labwc/rc.xml','personal keyboard/menu settings'),('etc/modprobe.d/macbook.conf','machine specific hardware fix'),('etc/NetworkManager/conf.d/macbook.conf','# personal network fix')]:
 path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value);protected[path]=path.read_bytes()
def commands(*args,answer=None):
 command=['chroot',str(root),*args]
 if answer is None:return subprocess.run(command,check=True,capture_output=True,text=True).stdout
 master,slave=os.openpty();process=subprocess.Popen(command,stdin=slave,stdout=slave,stderr=slave);os.close(slave);tail='';output='';deadline=time.monotonic()+180
 try:
  while process.poll() is None:
   if time.monotonic()>deadline:raise TimeoutError('APT interaction stalled')
   if not select.select([master],[],[],.2)[0]:continue
   try:data=os.read(master,65536)
   except OSError:break
   text=data.decode(errors='replace');output+=text;tail=(tail+text)[-600:]
   if 'Do you want to continue?' in tail:os.write(master,answer);tail=''
   elif '[default=N] ?' in tail:os.write(master,b'\n');tail=''
  code=process.wait(timeout=5)
 finally:
  os.close(master)
  if process.poll() is None:process.kill();process.wait()
 return code,output
script='/opt/erdos-source/scripts/enable-apt-updates.py'
commands('python3',script)
code,output=commands('python3',script,'--apply',answer=b'n\n')
assert code!=0 and 'Do you want to continue?' in output and (root/'var/lib/erdos/apt-migration/pending.json').exists(),output[-1500:]
assert (root/'usr/local/bin/labwc').exists()
print('CANCELLED_MIGRATION_PRESERVES_LEGACY_FILES',flush=True)
code,output=commands('python3',script,'--apply',answer=b'\n')
assert code==0,output[-5000:]
assert 'Resuming a previously checked migration' in output
assert '3 newly installed' in output and '0 to remove' in output,output[-5000:]
assert not (root/'var/lib/erdos/apt-migration/pending.json').exists()
assert (root/'usr/local/bin/labwc').is_symlink()
assert os.readlink(root/'usr/local/bin/labwc')=='/usr/bin/labwc'
assert '<openbox_pipe_menu>' in commands('/usr/local/bin/erdos-applications')
print(commands('/usr/local/bin/labwc','--version'),flush=True)
assert (root/'usr/bin/labwc').exists()
assert all(path.read_bytes()==value for path,value in protected.items())
assert 'Already package-managed' in commands('python3',script)
print(commands('dpkg-query','-W','erdos-desktop','erdos-labwc','erdos-archive-keyring'),flush=True)
print('PUBLIC_HTTPS_MIGRATION_RESUME_AND_PRESERVATION_PASSED',flush=True)
# A wrong archive key and tampered metadata must be rejected by the installed APT verifier.
sourcefile=root/'etc/apt/sources.list.d/erdos-updates.sources';original=sourcefile.read_text()
sourcefile.write_text(original.replace('/usr/share/keyrings/erdos-archive-keyring.asc','/usr/share/keyrings/debian-archive-keyring.gpg'))
for path in (root/'var/lib/apt/lists').glob('*downloads.erd.sh*'):path.unlink()
r=subprocess.run(['chroot',str(root),'apt-get','--error-on=any','update'],capture_output=True,text=True)
assert r.returncode!=0 and ('signature' in (r.stdout+r.stderr).lower() or 'key' in (r.stdout+r.stderr).lower()),r.stdout+r.stderr
sourcefile.write_text(original)
print('PUBLIC_APT_WRONG_KEY_REJECTED',flush=True)
