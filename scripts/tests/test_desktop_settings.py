#!/usr/bin/env python3
"""Configuration persistence and safety at the file/command boundary; no desktop writes."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / 'config/includes.chroot/usr/local/lib/erdos'


class DesktopSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='erdos-settings-test-')
        self.root = Path(self.temp.name)
        self.config = self.root / 'config'
        shutil.copytree(ROOT / 'config/includes.chroot/etc/skel/.config', self.config)
        self.bin = self.root / 'bin'; self.bin.mkdir()
        self.env = patch.dict(os.environ, HOME=str(self.root), XDG_CONFIG_HOME=str(self.config),
                              PATH=str(self.bin) + os.pathsep + os.environ['PATH'])
        self.env.start()
        self.addCleanup(self.env.stop); self.addCleanup(self.temp.cleanup)
        self.executable('labwc', '#!/bin/sh\n[ "${FAIL_RELOAD:-0}" = 0 ] || exit 1\nprintf "labwc test compositor\\n"\n')
        spec = importlib.util.spec_from_file_location('settings', LIB / 'settings.py')
        self.settings = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.settings)
        self.modules = patch.dict(sys.modules, settings=self.settings)
        self.modules.start(); self.addCleanup(self.modules.stop)
        spec = importlib.util.spec_from_file_location('display_settings', LIB / 'display_settings.py')
        self.displays = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.displays)

    def executable(self, name, content):
        path = self.bin / name; path.write_text(content); path.chmod(0o755)
        return path

    def test_cursor_persistence_and_failed_reload_restore_related_files(self):
        icons = self.root / 'icons/Test Cursor/cursors'; icons.mkdir(parents=True)
        with patch.dict(os.environ, XCURSOR_PATH=str(icons.parent.parent)):
            env = self.config / 'labwc/environment'
            env.write_text('CUSTOM=keep\nXKB_DEFAULT_LAYOUT=us\n')
            gtk = self.config / 'gtk-3.0/settings.ini'
            original = env.read_bytes(), gtk.read_bytes()
            with patch.dict(os.environ, FAIL_RELOAD='1'):
                with self.assertRaises(RuntimeError): self.settings.set_cursor('Test Cursor', 48)
            self.assertEqual((env.read_bytes(), gtk.read_bytes()), original)
            self.settings.set_cursor('Test Cursor', 48)
            self.assertEqual(self.settings.cursor_values(), ('Test Cursor', 48))
            self.assertIn('CUSTOM=keep', env.read_text())
            self.assertIn('gtk-font-name', gtk.read_text())
            self.assertTrue(gtk.with_name('settings.ini.previous').exists())

    def test_repeat_and_caps_preserve_layout_switching_and_shortcuts(self):
        env = self.config / 'labwc/environment'
        env.write_text('XKB_DEFAULT_LAYOUT=us,gb\nXKB_DEFAULT_OPTIONS=grp:win_space_toggle,numlock:mac,caps:escape\nCUSTOM=keep\n')
        original_keys = self.settings.keyboard()
        self.settings.set_keyboard_behavior(40, 300, 'ctrl:nocaps')
        self.assertEqual(self.settings.keyboard_behavior(), (40, 300, 'ctrl:nocaps'))
        self.assertEqual(self.settings.keyboard(), original_keys)
        self.assertIn('grp:win_space_toggle,numlock:mac,ctrl:nocaps', env.read_text())
        self.assertIn('XKB_DEFAULT_LAYOUT=us,gb', env.read_text())
        self.settings.set_keyboard_behavior(0, 600, 'default')
        self.assertIn('grp:win_space_toggle,numlock:mac', env.read_text())
        before = env.read_bytes()
        with self.assertRaises(ValueError): self.settings.set_keyboard_behavior(-1, 600, 'default')
        self.assertEqual(env.read_bytes(), before)

    def test_touchpad_options_preserve_other_device_configuration(self):
        import xml.etree.ElementTree as ET
        path = self.config / 'labwc/rc.xml'
        before = ET.parse(path).find('keyboard')
        prefs = self.settings.preferences()
        prefs.update(disable_while_typing=False, disable_on_mouse=True)
        self.settings.touchpad(prefs)
        tree = ET.parse(path)
        self.assertEqual(tree.findtext("libinput/device[@category='touchpad']/disableWhileTyping"), 'no')
        self.assertEqual(tree.findtext("libinput/device[@category='touchpad']/sendEventsMode"), 'disabledOnExternalMouse')
        self.assertEqual(ET.tostring(tree.find('keyboard')), ET.tostring(before))

    def mock_outputs(self):
        self.state = self.root / 'outputs.json'
        mode = dict(width=1280, height=800, refresh=60.0, preferred=True)
        items = [dict(name=name, enabled=enabled, modes=[{**mode, 'current': enabled}],
                      scale=1.0, position=dict(x=x, y=0), transform='normal')
                 for name, enabled, x in [('eDP-1', True, 0), ('HDMI-A-1', False, 1280)]]
        self.state.write_text(json.dumps(items))
        os.environ['ERDOS_TEST_OUTPUTS'] = str(self.state)
        self.addCleanup(os.environ.pop, 'ERDOS_TEST_OUTPUTS', None)
        self.executable('wlr-randr', '''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
p=Path(os.environ['ERDOS_TEST_OUTPUTS']); items=json.loads(p.read_text()); args=sys.argv[1:]
if args==['--json']: print(json.dumps(items));sys.exit(0)
by_name={item['name']:item for item in items};i=0
while i<len(args):
 key=args[i];i+=1
 if key=='--output': item=by_name[args[i]];i+=1
 elif key in ('--on','--off'):
  item['enabled']=key=='--on'
  for mode in item['modes']:mode['current']=item['enabled']
 elif key=='--mode':
  value=args[i];i+=1
  for mode in item['modes']:mode['current']=value==f"{mode['width']}x{mode['height']}@{mode['refresh']}Hz"
 elif key=='--scale':item['scale']=float(args[i]);i+=1
 elif key=='--transform':item['transform']=args[i];i+=1
 elif key=='--pos':item['position']=dict(zip(('x','y'),map(int,args[i].split(','))));i+=1
 else:raise ValueError(key)
p.write_text(json.dumps(items))
''')

    def trial(self, targets, answer):
        process = subprocess.Popen([sys.executable, '-B', str(LIB / 'display_settings.py')],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        process.stdin.write(json.dumps(targets) + '\n'); process.stdin.flush()
        ready = json.loads(process.stdout.readline())
        self.assertEqual(ready['status'], 'ready')
        process.stdin.write(answer + '\n');process.stdin.flush()
        stdout, stderr = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, stderr)
        return json.loads(stdout)['status']

    def test_display_enable_disable_confirm_restore_and_login_persistence(self):
        self.mock_outputs()
        items = self.displays.outputs()
        targets = {item['name']:self.displays.current_settings(item) for item in items}
        targets['eDP-1']['mode'] = None
        targets['HDMI-A-1']['mode'] = items[1]['preferred']
        # Cancelling must restore the previously enabled laptop output as well.
        self.assertEqual(self.trial(targets, 'revert'), 'restored')
        self.assertEqual([(item['name'], bool(item['mode'])) for item in self.displays.outputs()], [('eDP-1', True), ('HDMI-A-1', False)])
        self.assertEqual(self.trial(targets, 'keep'), 'kept')
        self.assertEqual([(item['name'], bool(item['mode'])) for item in self.displays.outputs()], [('eDP-1', False), ('HDMI-A-1', True)])
        prefs = self.settings.preferences()
        self.assertIsNone(prefs['display_modes']['configurations']['eDP-1']['mode'])
        # Simulate the compositor's next-login defaults; saved disabled states win.
        self.mock_outputs()
        self.displays.automatic()
        self.assertEqual([(item['name'], bool(item['mode'])) for item in self.displays.outputs()], [('eDP-1', False), ('HDMI-A-1', True)])
        for target in targets.values():target['mode']=None
        before=self.state.read_bytes()
        with self.assertRaisesRegex(ValueError, 'at least one'):self.displays.layout(self.displays.outputs(), targets)
        self.assertEqual(self.state.read_bytes(), before)

    def test_maintenance_allowlist_exit_status_and_interactive_commands(self):
        log=self.root/'sudo.json'
        with patch.dict(os.environ, ERDOS_TEST_SUDO=str(log)):
            self.executable('sudo', '''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
Path(os.environ['ERDOS_TEST_SUDO']).write_text(json.dumps(sys.argv[1:]))
sys.exit(int(os.environ.get('ERDOS_TEST_EXIT','0')))
''')
            helper=ROOT/'config/includes.chroot/usr/local/bin/erdos-maintenance'
            for action, command in [('update',['update']),('upgrade',['upgrade']),('autopurge',['autoremove','--purge']),('clean',['clean'])]:
                result=subprocess.run([str(helper),action],input='\n',capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(json.loads(log.read_text()),['--','apt-get',*command])
            log.unlink()
            self.assertEqual(subprocess.run([str(helper),'upgrade;touch bad'],capture_output=True).returncode,2)
            self.assertFalse(log.exists())
            with patch.dict(os.environ,ERDOS_TEST_EXIT='7'):
                self.assertEqual(subprocess.run([str(helper),'upgrade'],input='\n',capture_output=True,text=True).returncode,7)


if __name__=='__main__':unittest.main(verbosity=2)
