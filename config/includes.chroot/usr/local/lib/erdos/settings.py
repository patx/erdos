# SPDX-License-Identifier: MIT
"""Small, per-user settings backend. No service, shell commands or root access."""
import configparser
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
PREFERENCES = CONFIG / 'erdos/settings.json'
DEFAULTS = dict(terminal_app='system', background='#202326', background_image=False, background_layout='fill', natural=True, tapping=True, clickfinger=True,
                speed=0.0, automatic_displays=True, dynamic_workspaces=True, workspace_count=2, super_overview=True)
NS = 'http://openbox.org/3.4/rc'
ET.register_namespace('', NS)


def run(*args, input=None, timeout=20):
    result = subprocess.run(args, input=input, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout,
                            env={**os.environ, 'LC_ALL': 'C'})
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f'{args[0]} failed')
    return result.stdout.strip()


def write(path, content):
    """Atomic replacement, private new files, one previous version for recovery."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(path.name + '.previous')
        backup.write_bytes(path.read_bytes())
        backup.chmod(0o600)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(content)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def preferences():
    return {**DEFAULTS, **(json.loads(PREFERENCES.read_text()) if PREFERENCES.exists() else {})}


def save_preferences(**values):
    prefs = preferences()
    prefs.update(values)
    write(PREFERENCES, json.dumps(prefs, indent=2) + '\n')
    return prefs


def touchpad(prefs):
    result = subprocess.run(['erdos-touchpad', *[str(int(prefs[k])) for k in
                            ('natural', 'tapping', 'clickfinger')], str(prefs['speed'])],
                            text=True, capture_output=True, timeout=5)
    if result.returncode not in (0, 3):
        raise RuntimeError(result.stderr.strip() or 'Could not apply touchpad settings.')
    return result.stderr.strip()


WALLPAPER_MODES = {'fill': '-cover', 'fit': '-full', 'center': '-center', 'tile': '-tile'}


def wallpaper_path():
    return CONFIG / 'erdos/background-image'


def validate_background(path):
    # Use hsetroot's existing decoder; validate before touching the desktop.
    import ctypes as C
    imlib = C.CDLL('libImlib2.so.1')
    imlib.imlib_load_image.argtypes = [C.c_char_p]
    imlib.imlib_load_image.restype = C.c_void_p
    imlib.imlib_context_set_image.argtypes = [C.c_void_p]
    imlib.imlib_context_set_image.restype = None
    imlib.imlib_free_image_and_decache.argtypes = []
    imlib.imlib_free_image_and_decache.restype = None
    decoded = imlib.imlib_load_image(os.fsencode(path))
    if not decoded:
        raise ValueError('This file cannot be read as a supported image. Try PNG or JPEG.')
    imlib.imlib_context_set_image(decoded)
    imlib.imlib_free_image_and_decache()


def apply_background(prefs=None):
    prefs = preferences() if prefs is None else prefs
    color = prefs.get('background', DEFAULTS['background'])
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        color = DEFAULTS['background']
    path = wallpaper_path()
    if prefs.get('background_image') and path.is_file():
        try:
            validate_background(path)
            run('hsetroot', '-solid', color,
                WALLPAPER_MODES.get(prefs.get('background_layout'), '-cover'), str(path))
            return
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            pass  # Missing/failed wallpaper must never prevent desktop login.
    run('hsetroot', '-solid', color)


def set_background(color, image=False, layout='fill', source=None):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValueError('Choose a valid desktop color.')
    if layout not in WALLPAPER_MODES:
        raise ValueError('Choose a valid image layout.')
    path = wallpaper_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate = None
    try:
        if image:
            selected = Path(source).expanduser() if source else path
            if not selected.is_file():
                raise ValueError('Choose a readable image file first.')
            fd, name = tempfile.mkstemp(prefix='.background-', dir=path.parent)
            candidate = Path(name)
            with os.fdopen(fd, 'wb') as target, selected.open('rb') as original:
                shutil.copyfileobj(original, target)
            validate_background(candidate)
            run('hsetroot', '-solid', color, WALLPAPER_MODES[layout], str(candidate))
            os.replace(candidate, path)
        else:
            run('hsetroot', '-solid', color)
        save_preferences(background=color, background_image=bool(image), background_layout=layout)
        if not image:
            path.unlink(missing_ok=True)  # Only our private copy; never the user's original.
    finally:
        if candidate:
            candidate.unlink(missing_ok=True)


def appearance(theme, font, dark, color, image=False, layout='fill', source=None):
    set_background(color, image, layout, source)
    path = CONFIG / 'gtk-3.0/settings.ini'
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path)
    if not parser.has_section('Settings'):
        parser.add_section('Settings')
    parser['Settings'].update({'gtk-theme-name': theme, 'gtk-font-name': font,
                              'gtk-application-prefer-dark-theme': str(dark).lower()})
    stream = io.StringIO(); parser.write(stream); write(path, stream.getvalue())


def keyboard():
    path = CONFIG / 'openbox/rc.xml'
    tree = ET.parse(path)
    rows = []
    for bind in tree.findall(f'{{{NS}}}keyboard/{{{NS}}}keybind'):
        if bind.get('erdos-custom') == 'true':
            continue
        action = bind.find(f'{{{NS}}}action')
        command = action.findtext(f'{{{NS}}}command') if action is not None else None
        label = command or (action.get('name', '') if action is not None else '')
        target = action.findtext(f'{{{NS}}}to') if action is not None else None
        rows.append((bind.get('key', ''), label + (f' {target}' if target else '')))
    return rows


def custom_keyboard():
    tree = ET.parse(CONFIG / 'openbox/rc.xml')
    return [(bind.get('key', ''), bind.findtext(f'{{{NS}}}action/{{{NS}}}command', ''))
            for bind in tree.findall(f'{{{NS}}}keyboard/{{{NS}}}keybind')
            if bind.get('erdos-custom') == 'true']


def save_keyboard(keys, custom=None):
    tree = ET.parse(CONFIG / 'openbox/rc.xml')
    keyboard_node = tree.find(f'{{{NS}}}keyboard')
    binds = [b for b in keyboard_node.findall(f'{{{NS}}}keybind')
             if b.get('erdos-custom') != 'true']
    if custom is None:
        custom = custom_keyboard()
    for _, command in custom:
        if not command.strip() or any(ord(c) < 32 for c in command):
            raise ValueError('Every custom shortcut needs a command without control characters.')
    if len(keys) != len(binds):
        raise ValueError('Shortcuts changed outside Settings. Close and reopen Settings.')
    seen = set()
    for key in [*keys, *(key for key, _ in custom)]:
        if not key.strip():
            raise ValueError('Every action needs a shortcut.')
        for combo in key.split():
            if not re.fullmatch(r'(?:(?:W|A|C|S|M|H)-)*(?:[A-Za-z0-9_]+|0x[0-9a-fA-F]+)', combo):
                raise ValueError(f'Invalid shortcut: {combo}')
            # Canonical modifier ordering prevents duplicates such as W-S and S-W.
            parts = combo.split('-'); normalized = tuple(sorted(parts[:-1])) + (parts[-1],)
            if normalized in seen:
                raise ValueError(f'Shortcut used twice: {combo}')
            seen.add(normalized)
    for bind, key in zip(binds, keys):
        bind.set('key', key.strip())
    for bind in list(keyboard_node):
        if bind.get('erdos-custom') == 'true':
            keyboard_node.remove(bind)
    for key, command in custom:
        bind = ET.SubElement(keyboard_node, f'{{{NS}}}keybind',
                             {'key': key.strip(), 'erdos-custom': 'true'})
        action = ET.SubElement(bind, f'{{{NS}}}action', {'name': 'Execute'})
        ET.SubElement(action, f'{{{NS}}}command').text = command.strip()
    write(CONFIG / 'openbox/rc.xml', ET.tostring(tree.getroot(), encoding='unicode') + '\n')
    run('openbox', '--reconfigure')


def gestures():
    parser = configparser.ConfigParser()
    parser.read(['/etc/erdos/gestures.conf', CONFIG / 'erdos/gestures.conf'])
    return parser


def save_gestures(distance, bindings):
    parser = gestures()
    parser['swipe']['distance'] = str(distance)
    for key, action in bindings.items():
        parser['bindings'][key] = action
    stream = io.StringIO(); parser.write(stream)
    write(CONFIG / 'erdos/gestures.conf', stream.getvalue())
    run('erdos-gesture', 'reload')


def display_policy(enabled):
    save_preferences(automatic_displays=enabled)
    run('erdos-displays', '--stop')
    if enabled:
        run('erdos-displays', '--apply')
        from display_settings import restore_saved
        restore_saved()
        subprocess.Popen(['erdos-displays', '--watch-current'], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)


def apply_session():
    try:
        prefs = preferences()
    except (OSError, ValueError):
        prefs = DEFAULTS.copy()
    actions = [lambda: touchpad(prefs)]
    if prefs['automatic_displays']:
        actions.append(lambda: run('erdos-displays', '--apply'))
    from display_settings import restore_saved
    actions.append(restore_saved)
    actions.append(lambda: apply_background(prefs))
    for action in actions:
        try:
            action()
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            print(f'ErdOS settings: {error}', file=__import__('sys').stderr)
    if prefs['automatic_displays']:
        subprocess.Popen(['erdos-displays', '--watch-current'], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)


def audio_nodes():
    nodes = json.loads(run('pw-dump'))
    return [(str(n['id']), p.get('node.description', p.get('node.name', str(n['id']))),
             p.get('media.class')) for n in nodes
            if (p := n.get('info', {}).get('props', {})).get('media.class')
            in ('Audio/Sink', 'Audio/Source')]


def nm_lines(*args):
    # Escaping is required: SSIDs and connection names can contain colons/backslashes.
    text = run('nmcli', '-t', *args)
    rows = []
    for line in text.splitlines():
        fields, current, escaped = [], '', False
        for char in line:
            if escaped:
                current += char; escaped = False
            elif char == '\\':
                escaped = True
            elif char == ':':
                fields.append(current); current = ''
            else:
                current += char
        fields.append(current); rows.append(fields)
    return rows


def power_info():
    batteries, connected = [], False
    def read(device, name):
        try:
            return (device / name).read_text().strip()
        except OSError:
            return ''
    for device in sorted(Path('/sys/class/power_supply').glob('*')):
        kind = read(device, 'type')
        if kind == 'Battery':
            info = {'name':device.name, 'status':read(device,'status') or 'Unknown',
                    'capacity':read(device,'capacity'), 'cycles':read(device,'cycle_count')}
            for unit in ('energy','charge'):
                full, design = read(device,unit+'_full'), read(device,unit+'_full_design')
                if full.isdigit() and design.isdigit() and int(design):
                    info['health'] = round(100 * int(full)/int(design))
                    break
            batteries.append(info)
        elif read(device, 'online') == '1':
            connected = True
    return batteries, connected


MENU_NS = 'http://openbox.org/3.4/menu'


def menu_entries():
    """Keep original nodes so editing the root menu preserves nested/pipe menus."""
    source = (CONFIG / 'openbox/menu.xml').read_text()
    tree = ET.fromstring(source)
    root = tree.find(f"{{{MENU_NS}}}menu[@id='root-menu']")
    if root is None:
        raise ValueError('No root-menu found in Openbox menu.xml.')
    entries = []
    for node in root:
        actions = node.findall(f'{{{MENU_NS}}}action')
        editable = (node.tag == f'{{{MENU_NS}}}item' and len(actions) == 1
                    and actions[0].get('name') == 'Execute'
                    and actions[0].find(f'{{{MENU_NS}}}command') is not None)
        kind = 'Command' if editable else ('Separator' if node.tag == f'{{{MENU_NS}}}separator' else 'Built-in / submenu')
        command = actions[0].findtext(f'{{{MENU_NS}}}command', '') if editable else ''
        entries.append((node.get('label', ''), command, kind, ET.tostring(node, encoding='unicode')))
    return source, entries


def save_menu(source, entries):
    path = CONFIG / 'openbox/menu.xml'
    if path.read_text() != source:
        raise ValueError('The menu changed outside Settings. Close and reopen Settings before applying.')
    tree = ET.fromstring(source)
    root = tree.find(f"{{{MENU_NS}}}menu[@id='root-menu']")
    if root is None:
        raise ValueError('No root-menu found.')
    nodes = []
    for label, command, kind, original in entries:
        if kind not in ('Command', 'Separator', 'Built-in / submenu'):
            raise ValueError('Unknown menu entry type.')
        if kind != 'Separator' and not label.strip():
            raise ValueError('Every menu item needs a name.')
        if kind == 'Command' and (not command.strip() or any(ord(c) < 32 for c in command)):
            raise ValueError('Every command item needs a command without control characters.')
        if original:
            node = ET.fromstring(original)
        elif kind == 'Command':
            node = ET.Element(f'{{{MENU_NS}}}item')
            action = ET.SubElement(node, f'{{{MENU_NS}}}action', {'name': 'Execute'})
            ET.SubElement(action, f'{{{MENU_NS}}}command')
        elif kind == 'Separator':
            node = ET.Element(f'{{{MENU_NS}}}separator')
        else:
            raise ValueError('Built-in entries must come from the existing menu.')
        if label.strip():
            node.set('label', label.strip())
        else:
            node.attrib.pop('label', None)
        if kind == 'Command':
            node.find(f'{{{MENU_NS}}}action/{{{MENU_NS}}}command').text = command.strip()
        nodes.append(node)
    root[:] = nodes
    write(path, ET.tostring(tree, encoding='unicode') + '\n')
    run('openbox', '--reconfigure')
