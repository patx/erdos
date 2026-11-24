#!/usr/bin/env python3
"""Run build/test commands with scoped process, container and workspace cleanup."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
LOG_LIMIT = 8 * 1024 * 1024
LABEL = 'org.erdos.workspace'


def mounts_below(directory):
    mounts = []
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        name = re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), line.split()[4])
        path = Path(name)
        if path == directory or directory in path.parents:
            mounts.append(path)
    return sorted(set(mounts), key=lambda p: len(p.parts), reverse=True)


def remove_workspace(directory):
    """Never recurse into a mounted filesystem, even after a failed build."""
    for mount in mounts_below(directory):
        subprocess.run(['umount', '--', str(mount)], check=True, timeout=20)
    if mounts_below(directory):
        raise RuntimeError('Active mounts remain in ' + str(directory))
    # Keep the recovery marker until every disposable child has been removed.
    # A permission failure must not turn a managed leftover into an unknown tree.
    marker = directory / '.erdos-workspace.json'
    for child in directory.iterdir():
        if child == marker:
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    marker.unlink(missing_ok=True)
    directory.rmdir()


def append_log(log, data):
    log.write(data)
    if log.tell() > LOG_LIMIT:
        log.seek(-LOG_LIMIT // 2, os.SEEK_END)
        tail = log.read()
        log.seek(0)
        log.truncate()
        log.write(b'[Earlier output truncated; latest output follows]\n' + tail)
    log.flush()


def stop_group(process):
    if process is None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait()
        return
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            break
        time.sleep(.05)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def process_identity(pid):
    try:
        fields = Path('/proc/' + str(pid) + '/stat').read_text().rsplit(') ', 1)[1].split()
        return fields[19], fields[2], fields[0]  # start ticks, process group, state
    except FileNotFoundError:
        return None


def managed_owner(path):
    if os.geteuid() == 0:
        owner = ROOT.stat()
        os.chown(path, owner.st_uid, owner.st_gid)


def active_group(pgid):
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            identity = process_identity(int(path.name))
            if identity and identity[1] == str(pgid) and identity[2] != 'Z':
                return True
    return False


def recover_workspaces(work, docker):
    """Only recover our marked jobs after acquiring this checkout's run lock."""
    for directory in sorted(work.iterdir()):
        marker = directory / '.erdos-workspace.json'
        if directory.is_symlink() or not directory.is_dir() or not marker.is_file() or marker.is_symlink():
            continue
        info = json.loads(marker.read_text())
        if info.get('project') != str(ROOT) or not re.fullmatch(r'[a-f0-9]{32}', info.get('run', '')):
            continue
        same_boot = info.get('boot_id') == Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        if same_boot and info.get('pid_namespace') != os.readlink('/proc/self/ns/pid'):
            raise RuntimeError('Workspace was created in another PID namespace; inspect it in that environment: ' + str(directory))
        owner = process_identity(info['owner_pid']) if same_boot else None
        if owner and owner[0] == info['owner_start'] and owner[2] != 'Z':
            raise RuntimeError('Recorded workspace owner is still active: ' + str(directory))
        if info.get('container'):
            if not docker:
                raise RuntimeError('Use a Docker wrapper to recover its abandoned workspace: ' + str(directory))
            remove_container(info['container'], info['run'])
        pid = info.get('child_pid')
        if pid and same_boot:
            identity = process_identity(pid)
            if identity and identity[0] == info['child_start'] and identity[2] != 'Z':
                # The recorded session leader is still ours, not a reused PID.
                os.killpg(pid, signal.SIGTERM)
                time.sleep(.2)
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif identity and identity[2] != 'Z':
                raise RuntimeError('PID was reused; refusing automatic workspace removal: ' + str(directory))
            if active_group(pid):
                raise RuntimeError('Processes still use the abandoned workspace; refusing removal: ' + str(directory))
        remove_workspace(directory)
        print('Recovered abandoned workspace: ' + str(directory), flush=True)


def remove_container(name, token):
    if not name:
        return
    result = subprocess.run(['docker', 'inspect', '--format',
                             '{{index .Config.Labels "' + LABEL + '"}}', name],
                            capture_output=True, text=True, timeout=20)
    if result.returncode:
        # A stopped --rm container has already gone. An unavailable daemon is
        # an actual cleanup failure, not proof that the container disappeared.
        subprocess.run(['docker', 'info', '--format', '{{.ServerVersion}}'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=20)
        return
    if result.stdout.strip() != token:
        raise RuntimeError('Refusing to remove a container not owned by this run')
    subprocess.run(['docker', 'stop', '--time', '10', name], check=True,
                   stdout=subprocess.DEVNULL, timeout=20)


def publish_iso(candidate, checksum, destination):
    """Publish a verified worker result; rollback the prior pair on failure."""
    if destination.is_symlink():
        raise ValueError('Refusing a symlinked dist directory')
    destination.mkdir(exist_ok=True)
    if not candidate.is_file() or candidate.is_symlink() or candidate.stat().st_size == 0:
        raise ValueError('Missing regular ISO result')
    expected = checksum.read_text().split()[0]
    if not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ValueError('Invalid worker ISO checksum')
    image = destination / 'erdos-amd64.iso'
    sidecar = destination / 'erdos-amd64.iso.sha256'
    with tempfile.TemporaryDirectory(prefix='.erdos-publish-', dir=destination) as temporary:
        temporary = Path(temporary)
        staged = temporary / image.name
        shutil.copyfile(candidate, staged)
        with staged.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                raise ValueError('ISO copy does not match the verified worker checksum')
        staged_sum = temporary / sidecar.name
        staged_sum.write_text(expected + '  ' + image.name + '\n')
        previous = {}
        for target in (image, sidecar):
            if target.is_symlink():
                raise ValueError('Refusing a symlinked output file')
            if target.exists():
                backup = temporary / ('previous-' + target.name)
                try:
                    os.link(target, backup)
                except OSError:
                    # Root-built artifacts may be readable but not hardlinkable
                    # by a later ordinary-user Docker invocation.
                    shutil.copyfile(target, backup)
                previous[target] = backup
        try:
            os.replace(staged, image)
            os.replace(staged_sum, sidecar)
        except BaseException:
            for target in (image, sidecar):
                if target in previous:
                    os.replace(previous[target], target)
                else:
                    target.unlink(missing_ok=True)
            raise
    # Only generated ErdOS artifacts in this checkout's dist are eligible.
    # Never search Downloads, other projects, release directories or Docker caches.
    obsolete = {'SHA256SUMS', 'erdos-amd64.packages', 'erdos-build-project.zip',
                'erdos-build-project.zip.sha256', 'erdos-dev.json'}
    for path in destination.iterdir():
        old_iso = path.name.startswith('erdos') and (path.name.endswith('.iso') or path.name.endswith('.iso.sha256'))
        if path not in (image, sidecar) and (old_iso or path.name in obsolete):
            if path.is_file() or path.is_symlink():
                path.unlink()
    for path in (destination, image, sidecar):
        managed_owner(path)
    print('ISO: ' + str(image), flush=True)
    print('Checksum: ' + str(sidecar), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=('build', 'prepare', 'test'), required=True)
    parser.add_argument('--docker', action='store_true', help='Use a disposable Debian 13 container')
    parser.add_argument('--privileged', action='store_true', help='Allow live-build mounts/KVM inside Docker')
    parser.add_argument('--publish-iso', action='store_true', help='Publish the verified worker ISO result on success')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('Supply a command after --')
    if args.privileged and not args.docker:
        parser.error('--privileged requires --docker')
    if args.publish_iso and args.kind != 'build':
        parser.error('--publish-iso requires --kind build')
    # Linux directory locks work for both sudo and ordinary-user runs, without
    # leaving root-owned lock files or racing another build/test in this checkout.
    lock = os.open(ROOT, os.O_RDONLY)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock)
        parser.error('Another managed build/test is active in this checkout')
    work = ROOT / 'work'
    logs = ROOT / 'logs'
    if work.is_symlink() or logs.is_symlink():
        raise ValueError('Refusing a symlinked work/log directory')
    work.mkdir(exist_ok=True)
    logs.mkdir(exist_ok=True)
    managed_owner(work)
    managed_owner(logs)
    abandoned_publish = list((ROOT / 'dist').glob('.erdos-publish-*'))
    if abandoned_publish:
        raise ValueError('Interrupted ISO publication requires inspection before another run: '
                         + ', '.join(str(p) for p in abandoned_publish))
    recover_workspaces(work, args.docker)
    logfile = logs / ('latest-' + args.kind + '.log')
    if logfile.is_symlink():
        raise ValueError('Refusing a symlinked run log')
    logfile.unlink(missing_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix=args.kind + '-', dir=work))
    token = uuid.uuid4().hex
    marker = workspace / '.erdos-workspace.json'
    info = {'project': str(ROOT), 'run': token, 'kind': args.kind,
            'owner_pid': os.getpid(), 'owner_start': process_identity(os.getpid())[0],
            'pid_namespace': os.readlink('/proc/self/ns/pid'),
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    marker.write_text(json.dumps(info))
    environment = dict(os.environ, ERDOS_WORK_DIR=str(workspace), ERDOS_TEST_DIR=str(workspace))
    container = None
    process = None
    status = 1
    interrupted = None

    def interrupt(signum, _frame):
        nonlocal interrupted
        interrupted = signum
        raise RuntimeError('Interrupted by signal ' + str(signum))

    old_handlers = {s: signal.signal(s, interrupt) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        with logfile.open('w+b') as log:
            try:
                if args.kind == 'test':
                    (workspace / 'tmp').mkdir()
                    environment['TMPDIR'] = str(workspace / 'tmp')
                if args.docker:
                    container = 'erdos-' + args.kind + '-' + token
                    docker = ['docker', 'run', '--rm', '--name', container, '--label', LABEL + '=' + token]
                    if args.privileged:
                        docker += ['--privileged']
                    docker += ['--mount', 'type=bind,src=' + str(ROOT) + ',dst=/project,readonly',
                               '--mount', 'type=bind,src=' + str(workspace) + ',dst=/artifacts',
                               '--workdir', '/artifacts', '-e', 'ERDOS_WORK_DIR=/artifacts',
                               '-e', 'ERDOS_TEST_DIR=/artifacts',
                               '-e', 'ERDOS_OWNER=' + str(os.getuid()) + ':' + str(os.getgid()),
                               'debian:13', 'bash', '-c',
                               'trap \'result=$?; chown --no-dereference -R -- "$ERDOS_OWNER" /artifacts; exit "$result"\' EXIT; '
                               'setsid "$@" & job=$!; '
                               'trap \'kill -TERM -- -"$job" 2>/dev/null || :; wait "$job" || :; exit 130\' INT; '
                               'trap \'kill -TERM -- -"$job" 2>/dev/null || :; wait "$job" || :; exit 143\' TERM; '
                               'wait "$job"',
                               'erdos-job', *command]
                    command = docker
                    info['container'] = container
                    marker.write_text(json.dumps(info))
                process = subprocess.Popen(command, cwd=ROOT, env=environment,
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           start_new_session=True)
                identity = process_identity(process.pid)
                info.update(child_pid=process.pid, child_start=identity[0] if identity else '')
                marker.write_text(json.dumps(info))
                selector = selectors.DefaultSelector()
                os.set_blocking(process.stdout.fileno(), False)
                selector.register(process.stdout, selectors.EVENT_READ)
                while process.poll() is None:
                    for key, _ in selector.select(.1):
                        chunk = os.read(key.fd, 65536)
                        if chunk:
                            append_log(log, chunk)
                            sys.stdout.buffer.write(chunk)
                            sys.stdout.buffer.flush()
                        else:
                            selector.unregister(process.stdout)
                status = process.returncode
                stop_group(process)
                while chunk := process.stdout.read(65536):
                    append_log(log, chunk)
                    sys.stdout.buffer.write(chunk)
                selector.close()
                process.stdout.close()
                process = None
                info.pop('child_pid', None)
                marker.write_text(json.dumps(info))
                if status == 0 and args.publish_iso:
                    publish_iso(workspace / 'erdos-amd64.iso', workspace / 'erdos-amd64.iso.sha256', ROOT / 'dist')
            except (Exception, KeyboardInterrupt) as error:
                status = 128 + interrupted if interrupted else 1
                message = ('\nRun failed: ' + str(error) + '\n').encode()
                append_log(log, message)
                sys.stderr.buffer.write(message)
    finally:
        # Ignore a second Ctrl+C while our owned processes/mounts are stopped.
        for signum in old_handlers:
            signal.signal(signum, signal.SIG_IGN)
        try:
            stop_group(process)
            info.pop('child_pid', None)
            marker.write_text(json.dumps(info))
            remove_container(container, token)
            remove_workspace(workspace)
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            status = status or 1
            print('Cleanup incomplete; inspect ' + str(workspace) + ': ' + str(error), file=sys.stderr)
        finally:
            for signum, handler in old_handlers.items():
                signal.signal(signum, handler)
            os.close(lock)
            if logfile.exists():
                managed_owner(logfile)
        print('Latest log: ' + str(logfile), flush=True)
    return status if status >= 0 else 128 - status


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as error:
        sys.exit(str(error))
