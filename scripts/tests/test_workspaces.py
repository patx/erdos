#!/usr/bin/env python3
"""Exercise lifecycle/file-publication contracts with real child processes and files."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'run-workspace.py'


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='erdos-lifecycle-test-')
        self.root = Path(self.temporary.name)
        (self.root / 'scripts').mkdir()
        self.runner = self.root / 'scripts/run-workspace.py'
        shutil.copyfile(SOURCE, self.runner)
        self.dist = self.root / 'dist'
        self.dist.mkdir()
        self.image = self.dist / 'erdos-amd64.iso'
        self.image.write_bytes(b'previous verified worker result')
        self.sidecar = self.dist / 'erdos-amd64.iso.sha256'
        self.sidecar.write_text(hashlib.sha256(self.image.read_bytes()).hexdigest() + '  erdos-amd64.iso\n')
        self.original = self.image.read_bytes(), self.sidecar.read_bytes()
        self.processes = []

    def tearDown(self):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=3)
        self.temporary.cleanup()

    def command(self, code, *, kind='test', publish=False):
        return [sys.executable, str(self.runner), '--kind', kind,
                *(['--publish-iso'] if publish else []), '--', sys.executable, '-c', code]

    def run_code(self, code, *, kind='test', publish=False):
        return subprocess.run(self.command(code, kind=kind, publish=publish),
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=15)

    def start(self, code):
        process = subprocess.Popen(self.command(code), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.processes.append(process)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            log = self.root / 'logs/latest-test.log'
            if log.exists() and b'READY' in log.read_bytes():
                return process
            if process.poll() is not None:
                self.fail('Worker exited before ready')
            time.sleep(.03)
        self.fail('Worker did not become ready')

    def assert_clean(self):
        self.assertEqual(list((self.root / 'work').iterdir()), [])
        self.assertEqual(list(self.dist.glob('.erdos-publish-*')), [])

    def test_success_cleans_workspace_symlink_and_background_child(self):
        outside = self.root / 'outside'
        outside.mkdir(); (outside / 'keep').write_text('unrelated')
        code = ("import os,pathlib,subprocess; p=pathlib.Path(os.environ['ERDOS_TEST_DIR']); "
                "(p/'disk.qcow2').write_bytes(b'x'*1048576); "
                "(p/'outside').symlink_to(" + repr(str(outside)) + "); "
                "child=subprocess.Popen(['sleep','60']); print('CHILD='+str(child.pid),flush=True)")
        result = self.run_code(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_clean()
        self.assertEqual((outside / 'keep').read_text(), 'unrelated')
        pid = int((self.root / 'logs/latest-test.log').read_text().split('CHILD=')[1].split()[0])
        stat = Path('/proc') / str(pid) / 'stat'
        if stat.exists():
            self.assertEqual(stat.read_text().rsplit(') ', 1)[1].split()[0], 'Z')

    def test_failed_build_cleans_and_preserves_previous_image(self):
        result = self.run_code("import os,pathlib; (pathlib.Path(os.environ['ERDOS_WORK_DIR'])/'partial.iso').write_bytes(b'partial'); raise SystemExit(7)",
                               kind='build', publish=True)
        self.assertEqual(result.returncode, 7)
        self.assert_clean()
        self.assertEqual((self.image.read_bytes(), self.sidecar.read_bytes()), self.original)

    def test_publish_keeps_one_erdos_image_and_leaves_unrelated_files(self):
        (self.dist / 'erdos-old.iso').write_bytes(b'old')
        (self.dist / 'erdos-old.iso.sha256').write_text('old checksum')
        (self.dist / 'ubuntu.iso').write_bytes(b'not ours')
        outside = self.root / 'other-project'
        outside.mkdir(); (outside / 'erdos-old.iso').write_bytes(b'outside')
        result = self.run_code("import os,pathlib,hashlib; p=pathlib.Path(os.environ['ERDOS_WORK_DIR']); "
                               "data=b'new verified worker result'; (p/'erdos-amd64.iso').write_bytes(data); "
                               "(p/'erdos-amd64.iso.sha256').write_text(hashlib.sha256(data).hexdigest()+'  erdos-amd64.iso\\n')",
                               kind='build', publish=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_clean()
        self.assertEqual(self.image.read_bytes(), b'new verified worker result')
        self.assertEqual(self.sidecar.read_text().split()[0], hashlib.sha256(self.image.read_bytes()).hexdigest())
        self.assertFalse((self.dist / 'erdos-old.iso').exists())
        self.assertFalse((self.dist / 'erdos-old.iso.sha256').exists())
        self.assertEqual((self.dist / 'ubuntu.iso').read_bytes(), b'not ours')
        self.assertEqual((outside / 'erdos-old.iso').read_bytes(), b'outside')

    def test_bad_worker_checksum_preserves_previous_image_and_old_files(self):
        (self.dist / 'erdos-old.iso').write_bytes(b'old')
        result = self.run_code("import os,pathlib; p=pathlib.Path(os.environ['ERDOS_WORK_DIR']); "
                               "(p/'erdos-amd64.iso').write_bytes(b'bad copy'); "
                               "(p/'erdos-amd64.iso.sha256').write_text('0'*64)", kind='build', publish=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('does not match', result.stderr)
        self.assert_clean()
        self.assertEqual((self.image.read_bytes(), self.sidecar.read_bytes()), self.original)
        self.assertTrue((self.dist / 'erdos-old.iso').exists())

    def test_second_publication_write_failure_restores_previous_pair(self):
        spec = importlib.util.spec_from_file_location('workspace_under_test', self.runner)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        module.ROOT = self.root
        candidate = self.root / 'candidate.iso'; candidate.write_bytes(b'new data')
        checksum = self.root / 'candidate.sha256'; checksum.write_text(hashlib.sha256(candidate.read_bytes()).hexdigest())
        real_replace = os.replace
        failed = False
        def replace(source, destination):
            nonlocal failed
            if Path(destination) == self.sidecar and not failed:
                failed = True
                raise OSError('simulated sidecar write failure')
            return real_replace(source, destination)
        with patch.object(module.os, 'replace', side_effect=replace):
            with self.assertRaisesRegex(OSError, 'sidecar write failure'):
                module.publish_iso(candidate, checksum, self.dist)
        self.assertTrue(failed)
        self.assertEqual((self.image.read_bytes(), self.sidecar.read_bytes()), self.original)
        self.assertEqual(list(self.dist.glob('.erdos-publish-*')), [])

    def test_sigterm_cleans_files_and_children(self):
        process = self.start("import os,pathlib,time; (pathlib.Path(os.environ['ERDOS_TEST_DIR'])/'disk.qcow2').write_bytes(b'test'); print('READY',flush=True); time.sleep(60)")
        process.terminate(); process.wait(timeout=7)
        self.assertEqual(process.returncode, 143)
        self.assert_clean()
        self.assertEqual((self.image.read_bytes(), self.sidecar.read_bytes()), self.original)

    def test_next_run_recovers_marked_workspace_after_sigkill(self):
        process = self.start("import os,pathlib,time; (pathlib.Path(os.environ['ERDOS_TEST_DIR'])/'disk.qcow2').write_bytes(b'test'); print('READY',flush=True); time.sleep(60)")
        marker = next((self.root / 'work').glob('*/.erdos-workspace.json'))
        child = json.loads(marker.read_text())['child_pid']
        try:
            process.kill(); process.wait(timeout=3)
            self.assertTrue(marker.exists())
            result = self.run_code("print('recovered')")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assert_clean()
        finally:
            try: os.killpg(child, signal.SIGKILL)
            except ProcessLookupError: pass

    def test_second_run_cannot_remove_active_workspace(self):
        first = self.start("import time; print('READY',flush=True); time.sleep(60)")
        marker = next((self.root / 'work').glob('*/.erdos-workspace.json'))
        result = self.run_code("print('must not run')")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Another managed', result.stderr)
        self.assertTrue(marker.exists())
        first.terminate(); first.wait(timeout=7)
        self.assert_clean()

    def test_mounted_workspace_is_unmounted_before_removal(self):
        capabilities = next(line.split()[1] for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('CapEff:'))
        if os.geteuid() != 0 or not (int(capabilities, 16) & (1 << 21)):
            self.skipTest('Requires root and CAP_SYS_ADMIN in a disposable mount namespace')
        result = self.run_code("import os,pathlib,subprocess; p=pathlib.Path(os.environ['ERDOS_TEST_DIR'])/'mounted'; p.mkdir(); subprocess.run(['mount','-t','tmpfs','tmpfs',str(p)],check=True); (p/'file').write_text('mounted test data')")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_clean()
        self.assertNotIn(str(self.root / 'work') + '/', Path('/proc/self/mountinfo').read_text())

    @unittest.skipIf(os.geteuid() == 0, 'Root bypasses the filesystem permission failure')
    def test_cleanup_permission_failure_keeps_recovery_marker(self):
        result = self.run_code("import os,pathlib; p=pathlib.Path(os.environ['ERDOS_TEST_DIR'])/'private'; p.mkdir(); (p/'file').write_text('test'); p.chmod(0)")
        self.assertNotEqual(result.returncode, 0)
        marker = next((self.root / 'work').glob('*/.erdos-workspace.json'))
        self.assertTrue(marker.exists())
        (marker.parent / 'private').chmod(0o700)
        result = self.run_code("print('recovered after permission repair')")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_clean()

    def test_component_export_replaces_only_after_success_and_preserves_iso(self):
        packages=self.dist/'packages';packages.mkdir();(packages/'old.deb').write_bytes(b'previous build')
        def run(code):
            return subprocess.run([sys.executable,str(self.runner),'--kind','build','--publish-packages','--',sys.executable,'-c',code],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=15)
        code="import os,pathlib; p=pathlib.Path(os.environ['ERDOS_WORK_DIR'])/'packages'; p.mkdir(); (p/'new.deb').write_bytes(b'new component')"
        failed=run(code+"; raise SystemExit(9)")
        self.assertEqual(failed.returncode,9)
        self.assertEqual((packages/'old.deb').read_bytes(),b'previous build')
        success=run(code)
        self.assertEqual(success.returncode,0,success.stderr)
        self.assertEqual([p.name for p in packages.iterdir()],['new.deb'])
        self.assertEqual((packages/'new.deb').read_bytes(),b'new component')
        self.assertEqual((self.image.read_bytes(),self.sidecar.read_bytes()),self.original)
        self.assert_clean()

    def test_unmarked_directories_are_not_reaped_and_log_is_bounded(self):
        unmarked = self.root / 'work/unmanaged'
        unmarked.mkdir(parents=True); (unmarked / 'keep').write_text('unmanaged data')
        result = self.run_code("import os; os.write(1,b'x'*(20*1024*1024))")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLessEqual((self.root / 'logs/latest-test.log').stat().st_size, 8 * 1024 * 1024)
        self.assertEqual((unmarked / 'keep').read_text(), 'unmanaged data')
        self.assertEqual(list((self.root / 'work').iterdir()), [unmarked])


if __name__ == '__main__':
    unittest.main(verbosity=2)
