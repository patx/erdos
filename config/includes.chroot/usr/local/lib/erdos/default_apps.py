# SPDX-License-Identifier: MIT
"""Shared default-program discovery and launching; no resident service."""
import os
from pathlib import Path
import shutil
import subprocess

os.environ.setdefault('XDG_CURRENT_DESKTOP', 'Openbox')
from gi.repository import Gio
from settings import preferences, save_preferences

SYSTEM_TERMINAL = 'system'
# The associations are shared with GIO/xdg-mime and application preferences.
ROLES = {
    'terminal': ('Terminal', 'TerminalEmulator', (), None),
    'browser': ('Web Browser', 'WebBrowser',
                ('x-scheme-handler/https', 'x-scheme-handler/http', 'text/html', 'application/xhtml+xml'), 'firefox.desktop'),
    'files': ('File Manager', 'FileManager', ('inode/directory',), 'pcmanfm.desktop'),
    'editor': ('Text Editor', 'TextEditor', ('text/plain',), 'twig.desktop'),
}


def desktop_app(desktop_id):
    if not desktop_id:
        return None
    try:
        return Gio.DesktopAppInfo.new(desktop_id)
    except TypeError:
        # PyGObject reports a missing/invalid desktop entry as a NULL constructor.
        return None


def current(role):
    """Read associations at use time, including changes made outside Settings."""
    label, category, types, fallback = ROLES[role]
    if role == 'terminal':
        desktop_id = preferences().get('terminal_app')
        return desktop_app(desktop_id) if desktop_id != SYSTEM_TERMINAL else None
    for content_type in (types[:2] if role == 'browser' else types):
        app = Gio.AppInfo.get_default_for_type(content_type, False)
        if app:
            return app
    return desktop_app(fallback)


def choices(role):
    label, category, types, fallback = ROLES[role]
    apps = {}
    for app in Gio.AppInfo.get_all():
        if not app.get_id() or not app.should_show():
            continue
        categories = (app.get_categories() or '').split(';')
        if category in categories or set(types[:2] if role == 'browser' else types).intersection(app.get_supported_types() or ()):
            apps[app.get_id()] = app.get_display_name()
    selected = current(role)
    if selected and selected.get_id():
        apps[selected.get_id()] = selected.get_display_name()
    rows = sorted(apps.items(), key=lambda item: (item[1].casefold(), item[0]))
    if role == 'terminal':
        rows.insert(0, (SYSTEM_TERMINAL, 'System terminal'))
    return rows, selected.get_id() if selected else (SYSTEM_TERMINAL if role == 'terminal' else None)


def set_defaults(selections):
    # Validate every selection before writing any association.
    selected = {}
    for role, desktop_id in selections.items():
        if role not in ROLES:
            raise ValueError('Unknown default-program role: ' + role)
        if role == 'terminal' and desktop_id == SYSTEM_TERMINAL:
            selected[role] = None
            continue
        app = desktop_app(desktop_id)
        if app is None:
            raise ValueError(f'{ROLES[role][0]} is no longer installed. Refresh the application list.')
        selected[role] = app
    for role, app in selected.items():
        if role == 'terminal':
            save_preferences(terminal_app=app.get_id() if app else SYSTEM_TERMINAL)
        else:
            for content_type in ROLES[role][2]:
                if not app.set_as_default_for_type(content_type):
                    raise RuntimeError(f'Could not set {ROLES[role][0]}. Check permissions on your MIME preferences.')
    return 'Default programs saved. Menu entries and app shortcuts now use these choices.'


def launch(role):
    if role not in ROLES:
        raise ValueError('Unknown default-program role: ' + role)
    app = current(role)
    if role == 'terminal' and app is None:
        executable = shutil.which('x-terminal-emulator')
        if executable:
            subprocess.Popen([executable], cwd=Path.home())
            return
    if app is None:
        raise RuntimeError(f'No {ROLES[role][0].lower()} is available. Choose one in Settings → Default Programs.')
    files = [Gio.File.new_for_path(str(Path.home()))] if role == 'files' else []
    # GIO expands Desktop Entry field codes and respects quoted Exec/Path/Terminal.
    if not app.launch(files, None):
        raise RuntimeError(f'Could not launch {app.get_display_name()}. Choose another program in Settings → Default Programs.')
