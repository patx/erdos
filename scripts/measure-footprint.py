#!/usr/bin/env python3
"""Measure an installed, idle ErdOS desktop using only the Python standard library.

Run from another virtual console after logging in on tty1. Close application
windows first. Do not run apt update or install extra packages before sampling
a fresh installation. This reads system state and writes JSON only to stdout.
"""
import argparse
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def uptime():
    return float(Path('/proc/uptime').read_text().split()[0])


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    if Path('/run/live/medium').exists():
        sys.exit('Boot the installed disk without live media before measuring.')
    ready = uptime()
    print('Settling for 120 seconds, then taking five samples 10 seconds apart…',
          file=sys.stderr, flush=True)
    time.sleep(120)
    samples = []
    for index in range(5):
        memory = {key: int(value.split()[0]) * 1024 for key, value in
                  (line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())}
        samples.append(dict(uptime_seconds=uptime(), mem_total_bytes=memory['MemTotal'],
                            mem_available_bytes=memory['MemAvailable'],
                            used_bytes=memory['MemTotal'] - memory['MemAvailable']))
        if index < 4:
            time.sleep(10)
    filesystems = []
    for mount in ('/', '/boot/efi'):
        if mount != '/' and not Path(mount).is_mount():
            continue
        used, size = map(int, command('df', '-B1', '--output=used,size', mount).splitlines()[-1].split())
        filesystems.append(dict(mount=mount, used_bytes=used, filesystem_bytes=size))
    services = {}
    for service in ('NetworkManager', 'systemd-timesyncd', 'bluetooth'):
        services[service] = subprocess.run(['systemctl', 'is-active', service],
                                         capture_output=True, text=True).stdout.strip()
    result = dict(
        kernel=platform.release(), uefi=Path('/sys/firmware/efi').exists(),
        desktop_ready_uptime_seconds=ready, settle_seconds=120, sample_interval_seconds=10,
        ram_definition='MemTotal - MemAvailable', ram_samples=samples,
        ram_median_bytes=statistics.median(sample['used_bytes'] for sample in samples),
        filesystems=filesystems, disk_used_bytes=sum(fs['used_bytes'] for fs in filesystems),
        disk_definition='Used filesystem blocks on root and EFI; excludes swap and unallocated space',
        swap_proc_kib=Path('/proc/swaps').read_text().strip(), service_state=services,
        processes=command('ps', '-eo', 'comm,rss', '--sort=-rss'),
        apt_indexes_present=any(Path('/var/lib/apt/lists').glob('*Packages*')),
        release=Path('/etc/erdos-release').read_text().strip())
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
