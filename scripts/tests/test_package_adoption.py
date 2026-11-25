#!/usr/bin/env python3
"""Legacy adoption refuses local modifications before touching user machines."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]

class AdoptionTests(unittest.TestCase):
    def test_known_files_are_planned_and_local_fixes_are_rejected_without_writes(self):
        spec=importlib.util.spec_from_file_location('adoption',ROOT/'scripts/enable-apt-updates.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            binary=root/'usr/local/bin/labwc';binary.parent.mkdir(parents=True);binary.write_bytes(b'known compositor test fixture')
            record=root/'usr/local/share/doc/labwc/build.json';record.parent.mkdir(parents=True)
            pin=json.loads((ROOT/'vendor/labwc-fork.json').read_text())
            record.write_text(json.dumps({'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'labwc_source_sha256':pin['vendor_tree_sha256']}))
            # A real committed helper is recognized; arbitrary local edits are not.
            helper=root/'usr/local/bin/erdos-launch'
            helper.write_bytes((ROOT/'scripts/tests/fixtures/legacy-erdos-launch').read_bytes())
            home=root/'home/user/.config/labwc/rc.xml';home.parent.mkdir(parents=True);home.write_text('personal shortcuts')
            hardware=root/'etc/modprobe.d/macbook.conf';hardware.parent.mkdir(parents=True);hardware.write_text('machine-specific driver fix')
            plan=module.adoption_plan(root)
            self.assertIn('usr/local/bin/erdos-launch',plan)
            self.assertIn('usr/local/bin/labwc',plan)
            self.assertTrue(helper.exists())
            collision=root/'usr/bin/twig';collision.parent.mkdir(parents=True)
            collision.write_text('a locally installed editor')
            with self.assertRaisesRegex(ValueError,'Local modifications'):module.adoption_plan(root)
            self.assertEqual(collision.read_text(),'a locally installed editor')
            collision.unlink()
            helper.write_text('local desktop fix')
            with self.assertRaisesRegex(ValueError,'Local modifications'):module.adoption_plan(root)
            self.assertEqual(helper.read_text(),'local desktop fix')
            self.assertEqual(home.read_text(),'personal shortcuts')
            self.assertEqual(hardware.read_text(),'machine-specific driver fix')
            helper.unlink();helper.symlink_to(hardware)
            with self.assertRaises(ValueError):module.adoption_plan(root)
            self.assertEqual(hardware.read_text(),'machine-specific driver fix')

if __name__=='__main__':unittest.main(verbosity=2)
