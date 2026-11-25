#!/usr/bin/env python3
"""Upload a signed archive in APT-safe order to an explicitly scoped endpoint."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository',type=Path,required=True)
    p.add_argument('--endpoint',required=True)
    p.add_argument('--token-file',type=Path,required=True)
    args=p.parse_args()
    if not args.endpoint.startswith('https://'):p.error('Use an HTTPS endpoint')
    token=args.token_file.read_text().strip()
    manifest=json.loads((args.repository/'publication.json').read_text())
    def order(name):
        if name.endswith('/InRelease'):return 4
        if name.endswith('/Release.gpg'):return 3
        if name.endswith('/Release'):return 2
        return 0 if name.startswith('pool/') or '/by-hash/' in name else 1
    for name in sorted(manifest['files'],key=lambda name:(order(name),name)):
        path=args.repository/name
        if not path.resolve().is_relative_to(args.repository.resolve()) or path.is_symlink():raise ValueError('Unsafe publication path')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=manifest['files'][name]:raise ValueError('Artifact differs from publication manifest: '+name)
        for attempt in range(6):
            try:
                request=urllib.request.Request(args.endpoint.rstrip('/')+'/'+name,data=data,method='PUT',headers={'Authorization':'Bearer '+token,'User-Agent':'ErdOS-APT-Publish/1.0','Content-Type':'application/octet-stream'})
                with urllib.request.urlopen(request,timeout=90) as response:result=json.load(response)
                if not result.get('ok') or result.get('sha256')!=manifest['files'][name]:
                    raise RuntimeError('Endpoint did not acknowledge the exact uploaded digest')
                print('Published',name,flush=True);break
            except Exception as error:
                if isinstance(error,urllib.error.HTTPError) and error.code not in (408,429,500,502,503,504):raise
                if attempt==5:raise
                time.sleep(2**attempt)

if __name__=='__main__':main()
