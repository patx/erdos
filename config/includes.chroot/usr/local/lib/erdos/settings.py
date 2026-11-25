# SPDX-License-Identifier: MIT
"""Small, per-user settings backend. No resident service or root access."""
import configparser
import ctypes
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
DEFAULT_WALLPAPER = Path('/usr/share/erdos/backgrounds/default.png')
DEFAULTS = dict(terminal_app='system', background='#202326', background_image=False, background_layout='fill', natural=True, tapping=True, clickfinger=True,
                speed=0.0, disable_while_typing=True, disable_on_mouse=False,
                automatic_displays=True, dynamic_workspaces=True, workspace_count=2, super_overview=True, menu_touchpad=True, menu_mouse=True)
NS = ''


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
    saved = json.loads(PREFERENCES.read_text()) if PREFERENCES.exists() else {}
    return {**DEFAULTS, 'background_image': DEFAULT_WALLPAPER.is_file(), **saved}


def save_preferences(**values):
    prefs = preferences()
    prefs.update(values)
    write(PREFERENCES, json.dumps(prefs, indent=2) + '\n')
    session = configparser.ConfigParser()
    session['session'] = {key: str(prefs[key]).lower() for key in ('dynamic_workspaces', 'workspace_count', 'super_overview', 'menu_touchpad')}
    stream = io.StringIO(); session.write(stream)
    write(CONFIG / 'erdos/session.ini', stream.getvalue())
    return prefs


def touchpad(prefs):
    path, source, root = labwc_config()
    libinput = root.find('libinput')
    if libinput is None:
        libinput = ET.SubElement(root, 'libinput')
    device = next((d for d in libinput if d.get('category') == 'touchpad'), None)
    if device is None:
        device = ET.SubElement(libinput, 'device', {'category': 'touchpad'})
    values = {'naturalScroll': 'yes' if prefs['natural'] else 'no',
              'tap': 'yes' if prefs['tapping'] else 'no',
              'clickMethod': 'clickfinger' if prefs['clickfinger'] else 'buttonAreas',
              'tapButtonMap': 'lrm', 'clickfingerButtonMap': 'lrm',
              'pointerSpeed': str(prefs['speed']), 'scrollMethod': 'twofinger',
              'disableWhileTyping': 'yes' if prefs['disable_while_typing'] else 'no',
              'sendEventsMode': 'disabledOnExternalMouse' if prefs['disable_on_mouse'] else 'yes'}
    for key, value in values.items():
        node = device.find(key)
        if node is None:
            node = ET.SubElement(device, key)
        node.text = value
    update_labwc(path, source, ET.tostring(root, encoding='unicode') + '\n')



WALLPAPER_MODES = {'fill': 'fill', 'fit': 'fit', 'center': 'center', 'tile': 'tile'}


def wallpaper_path():
    return CONFIG / 'erdos/background-image'


def selected_wallpaper_path():
    custom = wallpaper_path()
    return custom if custom.is_file() else DEFAULT_WALLPAPER


def validate_background(path):
    import gi
    gi.require_version('GdkPixbuf', '2.0')
    from gi.repository import GdkPixbuf
    try:
        GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), 1, 1, True)
    except Exception as error:
        raise ValueError('This file cannot be decoded. Try PNG or JPEG.') from error


def apply_background(prefs=None):
    run('systemctl', '--user', 'restart', 'erdos-background.service')


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
            selected = Path(source).expanduser() if source else selected_wallpaper_path()
            if not selected.is_file():
                raise ValueError('Choose a readable image file first.')
            if source:
                fd, name = tempfile.mkstemp(prefix='.background-', dir=path.parent)
                candidate = Path(name)
                with os.fdopen(fd, 'wb') as target, selected.open('rb') as original:
                    shutil.copyfileobj(original, target)
                validate_background(candidate)
                os.replace(candidate, path)
            else:
                validate_background(selected)
        save_preferences(background=color, background_image=bool(image), background_layout=layout)
        if not image:
            path.unlink(missing_ok=True)  # Only our private copy; never the user's original.
        apply_background()
    finally:
        if candidate:
            candidate.unlink(missing_ok=True)


def desktop_appearance():
    from gi.repository import Gio
    source=Gio.SettingsSchemaSource.get_default()
    schema=source.lookup('org.gnome.desktop.interface',True) if source else None
    if schema is None or not schema.has_key('color-scheme'):
        return None
    return Gio.Settings.new_full(schema,None,None)


def prefers_dark(fallback=True):
    interface=desktop_appearance()
    value=interface.get_string('color-scheme') if interface else 'default'
    return True if value=='prefer-dark' else False if value=='prefer-light' else fallback


def set_color_scheme(dark, initialize=False):
    from gi.repository import Gio
    interface=desktop_appearance()
    if interface is None:
        raise RuntimeError('System color-scheme support is unavailable. Check gsettings-desktop-schemas.')
    if initialize and interface.get_user_value('color-scheme') is not None:
        return
    if not interface.set_string('color-scheme','prefer-dark' if dark else 'prefer-light'):
        raise RuntimeError('Could not save the system color scheme. Check your desktop settings permissions.')
    Gio.Settings.sync()


def theme_roots():
    user_data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    system_data = os.environ.get('XDG_DATA_DIRS') or '/usr/local/share:/usr/share:/opt/share'
    return (Path.home() / '.themes', user_data / 'themes',
            *(Path(path) / 'themes' for path in system_data.split(':') if path))


def theme_names(*patterns):
    return {path.parent.parent.name for root in theme_roots()
            for pattern in patterns for path in root.glob(pattern) if path.is_file()}


def icon_theme_names(search_paths):
    names = set()
    for search_path in search_paths:
        for path in Path(search_path).glob('*/index.theme'):
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(path)
                if parser.get('Icon Theme', 'Directories', fallback='').strip():
                    names.add(path.parent.name)
            except (configparser.Error, UnicodeError, OSError):
                continue
    return names


def update_labwc(path, source, updated):
    if source == updated:
        return
    write(path, updated)
    try:
        run('labwc', '--reconfigure')
    except Exception:
        if source is None:
            path.unlink(missing_ok=True)
        else:
            write(path, source)
        raise


def labwc_config():
    path = CONFIG / 'labwc/rc.xml'
    source = path.read_text() if path.exists() else None
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    root = ET.fromstring(source, parser) if source is not None else ET.Element('labwc_config')
    return path, source, root


def mouse_values():
    _, _, root = labwc_config()
    node = root.find("libinput/device[@category='non-touch']")
    value = node.findtext if node is not None else lambda key, default: default
    return dict(speed=float(value('pointerSpeed', '0')), scroll=float(value('scrollFactor', '1')),
                natural=value('naturalScroll', 'no') == 'yes', left=value('leftHanded', 'no') == 'yes',
                profile=value('accelProfile', '') or 'default')


def set_mouse(speed, scroll, natural, left, profile):
    if not (-1 <= speed <= 1 and 0.1 <= scroll <= 5 and profile in ('default', 'flat', 'adaptive')):
        raise ValueError('Invalid mouse settings.')
    path, source, root = labwc_config()
    libinput = root.find('libinput')
    if libinput is None:
        libinput = ET.SubElement(root, 'libinput')
    device = libinput.find("device[@category='non-touch']")
    if device is None:
        device = ET.SubElement(libinput, 'device', {'category': 'non-touch'})
    values = dict(pointerSpeed=f'{speed:.2f}', scrollFactor=f'{scroll:.2f}',
                  naturalScroll='yes' if natural else 'no', leftHanded='yes' if left else 'no',
                  accelProfile=profile if profile != 'default' else None)
    for key, value in values.items():
        node = device.find(key)
        if value is None:
            if node is not None:
                device.remove(node)
            continue
        if node is None:
            node = ET.SubElement(device, key)
        node.text = value
    update_labwc(path, source, ET.tostring(root, encoding='unicode') + '\n')


XKB_LAYOUT_KEYS = ('XKB_DEFAULT_LAYOUT', 'XKB_DEFAULT_VARIANT', 'XKB_DEFAULT_OPTIONS')


def keyboard_layout_options():
    catalog = ET.parse('/usr/share/X11/xkb/rules/evdev.xml')
    layouts = {}
    for node in catalog.findall('layoutList/layout'):
        name = node.findtext('configItem/name')
        layouts[name] = {v.text for v in node.findall('variantList/variant/configItem/name')}
    switches = {node.findtext('configItem/name'): node.findtext('configItem/description')
                for node in catalog.findall('optionList/group/option')
                if node.findtext('configItem/name', '').startswith('grp:')}
    return layouts, switches


def keyboard_environment(source):
    values = {key: os.environ.get(key, '') for key in XKB_LAYOUT_KEYS}
    for line in source.splitlines():
        key, _, value = line.partition('=')
        if key.strip() in values:
            values[key.strip()] = value.strip()
    return values


def keyboard_layout():
    path = CONFIG / 'labwc/environment'
    values = keyboard_environment(path.read_text() if path.exists() else '')
    layouts, variants, options = (values[key] for key in XKB_LAYOUT_KEYS)
    switch = next((option for option in options.split(',') if option.startswith('grp:')), '')
    return layouts or 'us', variants, switch


def set_keyboard_layout(layouts, variants, switch):
    catalog, switches = keyboard_layout_options()
    layouts = [value.strip() for value in layouts.split(',')]
    variants = [value.strip() for value in variants.split(',')] if variants.strip() else []
    if not 1 <= len(layouts) <= 4 or any(layout not in catalog for layout in layouts):
        raise ValueError('Enter one to four valid keyboard layout codes, such as us,gb.')
    if len(variants) > len(layouts) or any(variant and variant not in catalog[layout]
                                          for layout, variant in zip(layouts, variants)):
        raise ValueError('Enter variants in layout order, with commas for blank entries.')
    if switch and (switch not in switches or len(layouts) < 2):
        raise ValueError('Choose at least two layouts to use a switching shortcut.')
    path = CONFIG / 'labwc/environment'
    source = path.read_text() if path.exists() else None
    values = keyboard_environment(source or '')
    options = [value for value in values['XKB_DEFAULT_OPTIONS'].split(',')
               if value and not value.startswith('grp:')]
    if switch:
        options.append(switch)
    new_values = dict(zip(XKB_LAYOUT_KEYS, (','.join(layouts), ','.join(variants), ','.join(options))))
    lines = [line for line in (source or '').splitlines() if line.partition('=')[0].strip() not in new_values]
    lines.extend(f'{key}={value}' for key, value in new_values.items())
    update_labwc(path, source, '\n'.join(lines) + '\n')


def labwc_theme():
    path = CONFIG / 'labwc/rc.xml'
    return ET.parse(path).findtext('theme/name', '').strip() if path.exists() else ''


def set_labwc_theme(name):
    path, source, root = labwc_config()
    theme = root.find('theme')
    if theme is None:
        if not name:
            return
        theme = ET.SubElement(root, 'theme')
    node = theme.find('name')
    if name == theme.findtext('name', '').strip():
        return
    if not name:
        theme.remove(node)
    else:
        if node is None:
            node = ET.SubElement(theme, 'name')
        node.text = name
    update_labwc(path, source, ET.tostring(root, encoding='unicode') + '\n')


def set_gtk_appearance(theme, font, dark, icon_theme):
    path = CONFIG / 'gtk-3.0/settings.ini'
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path)
    if not parser.has_section('Settings'):
        parser.add_section('Settings')
    parser['Settings'].update({'gtk-theme-name': theme, 'gtk-font-name': font,
                              'gtk-application-prefer-dark-theme': str(dark).lower()})
    parser['Settings']['gtk-icon-theme-name'] = icon_theme
    stream = io.StringIO(); parser.write(stream); write(path, stream.getvalue())
    set_color_scheme(dark)


def accent_files():
    return (CONFIG / 'labwc/themerc-override', CONFIG / 'gtk-3.0/gtk.css')


def accent_block(path):
    source = path.read_text() if path.exists() else ''
    if path.name == 'gtk.css':
        begin, end = '/* ErdOS accent begin */', '/* ErdOS accent end */'
    else:
        begin, end = '# ErdOS accent begin', '# ErdOS accent end'
    pattern = re.compile(r'^' + re.escape(begin) + r'\n(.*?)^' + re.escape(end) + r'(?:\n|$)', re.M | re.S)
    return source, pattern, begin, end


def accents():
    colors = []
    shared = False
    for path in accent_files():
        source, pattern, _, _ = accent_block(path)
        block = pattern.search(source)
        color = re.search(r'#[0-9a-fA-F]{6}', block[1]) if block else None
        colors.append(color[0].lower() if color else None)
        if path.name == 'gtk.css' and block:
            shared = block[1].startswith('/* Follow the desktop accent */\n')
    return (*colors, shared)


def accent_foreground(color):
    rgb = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
              for value in rgb]
    luminance = sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    return '#000000' if luminance >= 0.179 else '#ffffff'


def save_accents(desktop, applications, shared=False):
    if shared:
        applications = desktop
    for color in (desktop, applications):
        if color is not None and not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValueError('Choose a valid accent color.')
    changes = []
    for path, color in zip(accent_files(), (desktop, applications)):
        source, pattern, begin, end = accent_block(path)
        updated = pattern.sub('', source)
        rules = ''
        if color:
            foreground = accent_foreground(color)
            if path.name == 'gtk.css':
                rules = (
                    f'@define-color theme_selected_bg_color {color};\n'
                    f'@define-color theme_selected_fg_color {foreground};\n'
                    'menu menuitem:hover, row:selected, .view:selected,\n'
                    'iconview cell:selected, treeview.view:selected, text selection,\n'
                    'switch:checked, check:checked, radio:checked, scale highlight,\n'
                    'progressbar progress, button.suggested-action {\n'
                    '  background-image: none;\n'
                    '  background-color: @theme_selected_bg_color;\n'
                    '  color: @theme_selected_fg_color;\n'
                    '}\n'
                )
            else:
                rules = (f'menu.items.active.bg.color: {color}\n'
                         f'menu.items.active.text.color: {foreground}\n')
        if path.name == 'gtk.css' and shared:
            rules = '/* Follow the desktop accent */\n' + rules
        if rules:
            if updated and not updated.endswith('\n'):
                updated += '\n'
            updated += f'{begin}\n{rules}{end}\n'
        if updated != source:
            changes.append((path, source if path.exists() else None, updated))

    written = []
    try:
        for path, previous, updated in changes:
            write(path, updated)
            written.append((path, previous))
        if any(path.name == 'themerc-override' for path, _, _ in changes):
            run('labwc', '--reconfigure')
    except Exception:
        for path, previous in reversed(written):
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                write(path, previous)
        raise


def keyboard():
    path = CONFIG / 'labwc/rc.xml'
    tree = ET.parse(path)
    rows = []
    for bind in tree.findall('keyboard/keybind'):
        if bind.get('erdos-custom') == 'true':
            continue
        action = bind.find('action')
        command = action.findtext('command') if action is not None else None
        label = command or (action.get('name', '') if action is not None else '')
        if action is not None and action.get('name') == 'ShowMenu':
            label = 'ShowMenu ' + action.findtext('menu','root-menu')
        if action is not None and action.get('name') == 'SnapToEdge':
            label = 'Tile ' + action.findtext('direction','')
        target = action.findtext('to') if action is not None else None
        rows.append((bind.get('key', ''), label + (f' {target}' if target else '')))
    return rows


def custom_keyboard():
    tree = ET.parse(CONFIG / 'labwc/rc.xml')
    return [(bind.get('key', ''), bind.findtext('action/command', ''))
            for bind in tree.findall('keyboard/keybind')
            if bind.get('erdos-custom') == 'true']


def shortcut_label(value):
    names = {'W':'Super', 'C':'Ctrl', 'A':'Alt', 'S':'Shift', 'M':'Mod5', 'H':'Mod3'}
    keys = {'Return':'Enter', 'space':'Space', 'Escape':'Esc'}
    return ' / '.join(' + '.join([*(names.get(p,p) for p in combo.split('-')[:-1]),
        keys.get(combo.split('-')[-1],combo.split('-')[-1].upper() if len(combo.split('-')[-1])==1 else combo.split('-')[-1])]) for combo in value.split())


def shortcut_value(value):
    value = re.sub(r'\s*\+\s*', '-', value.strip())
    value = re.sub(r'\s*[,/]\s*', ' ', value)
    modifiers = {'super':'W','ctrl':'C','control':'C','alt':'A','shift':'S','mod5':'M','mod3':'H'}
    keys = {'enter':'Return','esc':'Escape','space':'space'}
    result=[]
    for combo in value.split():
        parts=combo.split('-')
        result.append('-'.join([*(modifiers.get(p.lower(),p) for p in parts[:-1]),keys.get(parts[-1].lower(),parts[-1])]))
    return ' '.join(result)


def validate_shortcuts(values):
    # Use the same keysym lookup and lowercasing as labwc, including aliases.
    xkb = ctypes.CDLL('libxkbcommon.so.0')
    xkb.xkb_keysym_from_name.argtypes = [ctypes.c_char_p, ctypes.c_int]
    xkb.xkb_keysym_from_name.restype = ctypes.c_uint32
    xkb.xkb_keysym_to_lower.argtypes = [ctypes.c_uint32]
    xkb.xkb_keysym_to_lower.restype = ctypes.c_uint32
    seen=set()
    for value in values:
        if not value.strip():
            raise ValueError('Every action needs a shortcut.')
        for combo in value.split():
            if not re.fullmatch(r'(?:(?:W|A|C|S|M|H)-)*[A-Za-z0-9_]+',combo):
                raise ValueError(f'Invalid shortcut: {combo}. Use a key name such as Return or F1.')
            parts=combo.split('-')
            if parts[-1].lower().startswith('0x'):
                raise ValueError('Use key names instead of X11 keycodes.')
            symbol=xkb.xkb_keysym_to_lower(xkb.xkb_keysym_from_name(parts[-1].encode(),1))
            if not symbol:
                raise ValueError(f'Unknown key name: {parts[-1]}')
            normalized=(frozenset(parts[:-1]),symbol)
            if normalized in seen:
                raise ValueError(f'Shortcut used twice: {shortcut_label(combo)}')
            seen.add(normalized)


def keyboard_source():
    node=ET.parse(CONFIG / 'labwc/rc.xml').find('keyboard')
    return ET.canonicalize(ET.tostring(node,encoding='unicode'),strip_text=True)


def save_keyboard(keys, custom=None, original=None):
    tree = ET.parse(CONFIG / 'labwc/rc.xml')
    keyboard_node = tree.find('keyboard')
    if original is not None and keyboard_source()!=original:
        raise ValueError('Shortcuts changed outside this editor. Close and reopen Settings before applying.')
    binds = [b for b in keyboard_node.findall('keybind')
             if b.get('erdos-custom') != 'true']
    if custom is None:
        custom = custom_keyboard()
    for _, command in custom:
        if not command.strip() or any(ord(c) < 32 for c in command):
            raise ValueError('Every custom shortcut needs a command without control characters.')
    if len(keys) != len(binds):
        raise ValueError('Shortcuts changed outside Settings. Close and reopen Settings.')
    validate_shortcuts([*keys, *(key for key, _ in custom)])
    for bind, key in zip(binds, keys):
        bind.set('key', key.strip())
    for bind in list(keyboard_node):
        if bind.get('erdos-custom') == 'true':
            keyboard_node.remove(bind)
    for key, command in custom:
        bind = ET.SubElement(keyboard_node, 'keybind',
                             {'key': key.strip(), 'erdos-custom': 'true'})
        action = ET.SubElement(bind, 'action', {'name': 'Execute'})
        ET.SubElement(action, 'command').text = command.strip()
    write(CONFIG / 'labwc/rc.xml', ET.tostring(tree.getroot(), encoding='unicode') + '\n')
    run('labwc', '--reconfigure')


def menu_triggers(touchpad_menu, mouse_menu):
    path = CONFIG / 'labwc/rc.xml'
    tree = ET.parse(path)
    mouse = tree.getroot().find('mouse')
    if mouse is None:
        raise ValueError('labwc configuration has no mouse section.')
    # Only replace bindings owned by this feature; keep window actions intact.
    for context in mouse.findall('context'):
        for binding in list(context):
            if binding.get('erdos-menu') == 'yes':
                context.remove(binding)
    for name in ('Frame', 'Desktop'):
        context = next((node for node in mouse if node.get('name') == name), None)
        if context is None:
            context = ET.SubElement(mouse, 'context', {'name': name})
        for button, enabled in (('Task', touchpad_menu), ('W-Right', mouse_menu)):
            if enabled:
                binding = ET.SubElement(context, 'mousebind',
                    {'button': button, 'action': 'Press', 'erdos-menu': 'yes'})
                action = ET.SubElement(binding, 'action', {'name': 'ShowMenu'})
                ET.SubElement(action, 'menu').text = 'root-menu'
    write(path, ET.tostring(tree.getroot(), encoding='unicode') + '\n')
    run('labwc', '--reconfigure')
    prefs = save_preferences(menu_touchpad=bool(touchpad_menu), menu_mouse=bool(mouse_menu))
    return touchpad(prefs) or 'Menu triggers applied.'


def startup_file():
    path = CONFIG / 'labwc/autostart'
    if path.exists():
        return path.read_text()
    for fallback in (Path('/etc/skel/.config/labwc/autostart'), Path('/etc/xdg/labwc/autostart')):
        if fallback.is_file():
            return fallback.read_text()
    return '#!/bin/sh\n'


def save_startup(original, content):
    if startup_file() != original:
        raise ValueError('Startup configuration changed outside Settings. Reload before saving.')
    if '\0' in content:
        raise ValueError('Startup commands cannot contain NUL characters.')
    content = content if content.endswith('\n') else content + '\n'
    # Parse only: saving must never execute startup commands.
    run('sh', '-n', input=content)
    write(CONFIG / 'labwc/autostart', content)
    return 'Startup commands saved. They will run at your next desktop login.'


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
    run('labwc', '--reconfigure')


def display_policy(enabled):
    save_preferences(automatic_displays=enabled)
    run('labwc', '--reconfigure')
    if enabled:
        run('erdos-displays', '--apply')


def apply_session():
    # Publish a default on first login; preserve a later explicit system choice.
    parser=configparser.ConfigParser(interpolation=None)
    parser.read(CONFIG / 'gtk-3.0/settings.ini')
    dark=parser.getboolean('Settings','gtk-application-prefer-dark-theme',fallback=True)
    set_color_scheme(dark,initialize=True)
    # The compositor owns gestures/workspaces; only the background is resident.
    apply_background()
    run('erdos-displays', '--apply')


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


MENU_NS = ''


def menu_entries():
    """Keep original nodes so editing the root menu preserves nested/pipe menus."""
    source = (CONFIG / 'labwc/menu.xml').read_text()
    tree = ET.fromstring(source)
    root = tree.find("menu[@id='root-menu']")
    if root is None:
        raise ValueError('No root-menu found in labwc menu.xml.')
    entries = []
    for node in root:
        actions = node.findall('action')
        editable = (node.tag == 'item' and not node.get('erdos-status') and len(actions) == 1
                    and actions[0].get('name') == 'Execute'
                    and actions[0].find('command') is not None)
        kind = 'Command' if editable else ('Separator' if node.tag == 'separator' else 'Built-in / submenu')
        command = actions[0].findtext('command', '') if editable else ''
        entries.append((node.get('label', ''), command, kind, ET.tostring(node, encoding='unicode')))
    return source, entries


def save_menu(source, entries):
    path = CONFIG / 'labwc/menu.xml'
    if path.read_text() != source:
        raise ValueError('The menu changed outside Settings. Close and reopen Settings before applying.')
    tree = ET.fromstring(source)
    root = tree.find("menu[@id='root-menu']")
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
            node = ET.Element('item')
            action = ET.SubElement(node, 'action', {'name': 'Execute'})
            ET.SubElement(action, 'command')
        elif kind == 'Separator':
            node = ET.Element('separator')
        else:
            raise ValueError('Built-in entries must come from the existing menu.')
        if label.strip():
            node.set('label', label.strip())
        else:
            node.attrib.pop('label', None)
        if kind == 'Command':
            node.find('action/command').text = command.strip()
        nodes.append(node)
    root[:] = nodes
    write(path, ET.tostring(tree, encoding='unicode') + '\n')
    run('labwc', '--reconfigure')


def apply_desktop_files(changes):
    """Save related per-user settings together; restore them if reload fails."""
    written = []
    try:
        for path, previous, updated in changes:
            actual = path.read_text() if path.exists() else None
            if actual != previous:
                raise ValueError('Configuration changed outside Settings. Reopen this section before saving.')
            if previous != updated:
                write(path, updated)
                written.append((path, previous))
        run('labwc', '--reconfigure')
    except Exception:
        for path, previous in reversed(written):
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                write(path, previous)
        # Reload restored files as well, if the compositor is reachable.
        try:
            run('labwc', '--reconfigure')
        except Exception:
            pass
        raise


def environment_changes(values):
    path = CONFIG / 'labwc/environment'
    source = path.read_text() if path.exists() else None
    lines = [line for line in (source or '').splitlines()
             if line.partition('=')[0].strip() not in values]
    lines.extend(f'{key}={value}' for key, value in values.items())
    return path, source, '\n'.join(lines) + '\n'


def cursor_themes():
    paths = os.environ.get('XCURSOR_PATH')
    roots = [Path(os.path.expandvars(part)).expanduser() for part in paths.split(':') if part] if paths else [
        Path.home() / '.local/share/icons', Path.home() / '.icons',
        Path('/usr/share/icons'), Path('/usr/share/pixmaps'), Path.home() / '.cursors',
        Path('/usr/share/cursors/xorg-x11'), Path('/usr/X11R6/lib/X11/icons')]
    return {path.parent.name for root in roots for path in root.glob('*/cursors') if path.is_dir()}


def cursor_values():
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(CONFIG / 'gtk-3.0/settings.ini')
    path = CONFIG / 'labwc/environment'
    env = dict(line.split('=', 1) for line in path.read_text().splitlines()
               if '=' in line and not line.lstrip().startswith('#')) if path.exists() else {}
    theme = env.get('XCURSOR_THEME', parser.get('Settings', 'gtk-cursor-theme-name', fallback='Adwaita')).strip()
    size = int(env.get('XCURSOR_SIZE', parser.get('Settings', 'gtk-cursor-theme-size', fallback='24')))
    return theme, size


def set_cursor(theme, size):
    if theme not in cursor_themes() or not re.fullmatch(r'[\w. +()-]+', theme):
        raise ValueError('Choose an installed cursor theme.')
    if type(size) is not int or not 16 <= size <= 96:
        raise ValueError('Choose a cursor size between 16 and 96 pixels.')
    path = CONFIG / 'gtk-3.0/settings.ini'
    source = path.read_text() if path.exists() else None
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(source or '')
    if not parser.has_section('Settings'):
        parser.add_section('Settings')
    parser['Settings'].update({'gtk-cursor-theme-name': theme, 'gtk-cursor-theme-size': str(size)})
    stream = io.StringIO(); parser.write(stream)
    apply_desktop_files([environment_changes({'XCURSOR_THEME': theme, 'XCURSOR_SIZE': str(size)}),
                         (path, source, stream.getvalue())])
    return 'Cursor saved. Reopen applications that still show their previous cursor.'


CAPS_OPTIONS = {'default': 'Default', 'caps:swapescape': 'Swap Caps Lock and Esc',
                'ctrl:nocaps': 'Caps Lock acts as Ctrl', 'caps:escape': 'Caps Lock acts as Esc',
                'caps:none': 'Disable Caps Lock', 'custom': 'Keep custom mapping'}


def keyboard_behavior():
    _, _, root = labwc_config()
    path = CONFIG / 'labwc/environment'
    options = keyboard_environment(path.read_text() if path.exists() else '')['XKB_DEFAULT_OPTIONS'].split(',')
    caps = [option for option in options if option.startswith('caps:') or option in ('ctrl:nocaps', 'ctrl:swapcaps')]
    current = caps[0] if len(caps) == 1 and caps[0] in CAPS_OPTIONS else 'custom' if caps else 'default'
    return int(root.findtext('keyboard/repeatRate', '25')), int(root.findtext('keyboard/repeatDelay', '600')), current


def set_keyboard_behavior(rate, delay, caps):
    if type(rate) is not int or type(delay) is not int or not (0 <= rate <= 100 and 100 <= delay <= 2000) or caps not in CAPS_OPTIONS:
        raise ValueError('Invalid repeat or Caps Lock settings.')
    path, source, root = labwc_config()
    keyboard = root.find('keyboard')
    if keyboard is None:
        keyboard = ET.SubElement(root, 'keyboard')
    for key, value in {'repeatRate': rate, 'repeatDelay': delay}.items():
        node = keyboard.find(key)
        if node is None:
            node = ET.SubElement(keyboard, key)
        node.text = str(value)
    changes = [(path, source, ET.tostring(root, encoding='unicode') + '\n')]
    if caps != 'custom':
        env_path = CONFIG / 'labwc/environment'
        env = keyboard_environment(env_path.read_text() if env_path.exists() else '')
        options = [option for option in env['XKB_DEFAULT_OPTIONS'].split(',') if option
                   and not option.startswith('caps:') and option not in ('ctrl:nocaps', 'ctrl:swapcaps')]
        if caps != 'default':
            options.append(caps)
        changes.append(environment_changes({'XKB_DEFAULT_OPTIONS': ','.join(options)}))
    apply_desktop_files(changes)


def system_information():
    """On-demand report, deliberately excluding hostnames, serials and addresses."""
    import platform
    def read(path):
        try:
            return Path(path).read_text().strip()
        except OSError:
            return ''
    release = read('/etc/erdos-release') or read('/etc/os-release')
    values = dict(line.split('=', 1) for line in release.splitlines() if '=' in line)
    model = ' '.join(value for value in (read('/sys/class/dmi/id/sys_vendor'), read('/sys/class/dmi/id/product_name')) if value)
    cpu = next((line.split(':', 1)[1].strip() for line in read('/proc/cpuinfo').splitlines() if line.startswith(('model name', 'Hardware'))), platform.machine())
    memory = next((int(line.split()[1]) * 1024 for line in read('/proc/meminfo').splitlines() if line.startswith('MemTotal:')), 0)
    try:
        compositor = run('labwc', '--version', timeout=3)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        compositor = 'Unavailable'
    usage = shutil.disk_usage('/')
    return '\n'.join([
        values.get('NAME', 'ErdOS').strip('"') + ' ' + values.get('VERSION', values.get('VERSION_ID', 'unknown')).strip('"'),
        'Build date: ' + values.get('BUILD_DATE', 'unknown'),
        'Kernel: ' + platform.release(), 'Architecture: ' + platform.machine(),
        'Computer: ' + (model or 'Not reported'), 'Processor: ' + cpu,
        f'Memory: {memory / 1024**3:.2f} GiB',
        f'Root filesystem: {usage.used / 1024**3:.2f} GiB used / {usage.total / 1024**3:.2f} GiB total',
        'Firmware boot: ' + ('UEFI' if Path('/sys/firmware/efi').exists() else 'BIOS / not reported'),
        'Desktop: ' + os.environ.get('XDG_CURRENT_DESKTOP', 'unknown'),
        'Session: ' + os.environ.get('XDG_SESSION_TYPE', 'unknown'), 'Compositor: ' + compositor,
    ])


def launch_maintenance(action):
    if action not in ('update', 'upgrade', 'autopurge', 'clean'):
        raise ValueError('Unknown maintenance action.')
    # Debian's terminal-emulator interface accepts -e followed by an argument vector.
    # No shell expansion, root GUI, password storage, or unattended -y option.
    terminal = shutil.which('x-terminal-emulator')
    helper = shutil.which('erdos-maintenance')
    if not terminal or not helper:
        raise RuntimeError('Install a system terminal and the ErdOS maintenance helper first.')
    subprocess.Popen([terminal, '-e', helper, action], cwd=Path.home())
    return 'Opened in the system terminal. Review its output and any confirmation prompts.'
