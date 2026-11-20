# SPDX-License-Identifier: MIT
"""Network controls with current state, explicit actions and event-driven refresh."""
import threading
from gi.repository import Gio, GLib, Gtk
import settings as backend


def snapshot():
    devices = backend.nm_lines('-f', 'DEVICE,TYPE,STATE,CONNECTION', 'device', 'status')
    wifi = [row for row in devices if row[1] == 'wifi']
    radio = backend.run('nmcli', 'radio', 'wifi') == 'enabled'
    profiles = [row for row in backend.nm_lines('-f', 'UUID,NAME,TYPE,ACTIVE', 'connection', 'show')
                if row[2] in ('wifi', '802-11-wireless')]
    aps = backend.nm_lines('-f', 'IN-USE,BSSID,SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list', '--rescan', 'no') if wifi and radio else []
    return dict(devices=devices, wifi=wifi, radio=radio, profiles=profiles, aps=aps,
                internet=backend.run('nmcli', '-g', 'CONNECTIVITY', 'general'))


def summary(info):
    if not info['wifi']:
        return 'No Wi-Fi adapter detected.'
    if not info['radio']:
        return 'Wi-Fi is off.'
    connected = [row for row in info['wifi'] if row[2].startswith('connected')]
    if connected:
        names = list(dict.fromkeys(row[3] for row in connected))
        return 'Connected to ' + ', '.join(f'“{name}”' for name in names) + '.'
    states = [row[2] for row in info['wifi']]
    if any(state.startswith('connecting') for state in states):
        return 'Connecting to Wi-Fi…'
    if 'failed' in states:
        return 'Wi-Fi connection failed. Check the password and try again.'
    if all(state == 'unmanaged' for state in states):
        return 'Wi-Fi is not managed by NetworkManager.'
    if all(state in ('unavailable', 'unmanaged') for state in states):
        return 'Wi-Fi is unavailable. Check airplane mode or the wireless switch.'
    return 'Wi-Fi is on. Not connected to a network.'


class Network:
    def __init__(self, app, page):
        self.app, self.page = app, page
        self.closed = self.ready = self.busy = self.refreshing = False
        self.timer = self.bus = self.subscription = None
        self.info = None
        self.revision = 0
        self.refresh_again = False
        self.last_message = None
        app.window.connect('destroy', self.close)
        app.stack.connect('notify::visible-child-name', self.tab_changed)
        app.load_section(page, snapshot, self.populate)
        Gio.bus_get(Gio.BusType.SYSTEM, None, self.got_bus)

    def populate(self, page, info):
        self.status = self.app.note(page, '')
        self.internet = self.app.note(page, '')
        self.wired = self.app.note(page, '')
        controls = Gtk.Box(spacing=8)
        page.pack_start(controls, False, False, 0)
        self.radio = Gtk.Button()
        self.radio.connect('clicked', self.toggle_radio)
        controls.pack_start(self.radio, False, False, 0)
        self.disconnect = Gtk.Button(label='Disconnect Wi-Fi')
        self.disconnect.connect('clicked', self.disconnect_wifi)
        controls.pack_start(self.disconnect, False, False, 0)
        self.networks = self.app.choice(page, 'Available Wi-Fi networks', [])
        self.password = self.app.row(page, 'Password (if needed)', Gtk.Entry(
            visibility=False, input_purpose=Gtk.InputPurpose.PASSWORD))
        self.scan = Gtk.Button(label='Scan for networks', halign=Gtk.Align.START)
        self.scan.connect('clicked', self.scan_networks)
        controls.pack_start(self.scan, False, False, 0)
        self.connect = Gtk.Button(label='Connect to selected network', halign=Gtk.Align.START)
        self.connect.connect('clicked', self.connect_network)
        page.pack_start(self.connect, False, False, 0)
        self.saved = self.app.choice(page, 'Saved Wi-Fi connection', [])
        self.saved_connect = Gtk.Button(label='Connect saved network', halign=Gtk.Align.START)
        self.saved_connect.connect('clicked', self.connect_saved)
        page.pack_start(self.saved_connect, False, False, 0)
        self.networks.connect('changed', lambda *_: self.sensitivity())
        self.saved.connect('changed', lambda *_: self.sensitivity())
        button = Gtk.Button(label='Refresh status', halign=Gtk.Align.START)
        button.connect('clicked', lambda *_: self.operation(lambda: None, 'Refreshing network status…', lambda info: 'Network status refreshed.'))
        page.pack_start(button, False, False, 0)
        self.app.note(page, 'Wi-Fi connection and internet access are shown separately. Leave the password empty for an open or saved network. Enterprise Wi-Fi and advanced profiles use Network Connections in Applications.')
        self.ready = True
        self.update(info)

    def update(self, info):
        if self.closed or not self.ready:
            return
        old = summary(self.info) if self.info else None
        self.info = info
        text = summary(info)
        self.status.set_text(text)
        self.internet.set_text('Internet: ' + {
            'full': 'available.', 'portal': 'sign-in required. Open a browser.',
            'limited': 'limited or unavailable.', 'none': 'no access reported.',
        }.get(info['internet'], 'not checked.'))
        wired = [row[3] for row in info['devices'] if row[1] == 'ethernet' and row[2].startswith('connected')]
        self.wired.set_text('Wired: ' + ', '.join(f'“{name}”' for name in wired) + '.' if wired else '')
        self.radio.set_label('Turn Wi-Fi off' if info['radio'] else 'Turn Wi-Fi on')
        selected = self.networks.get_active_id()
        self.networks.remove_all()
        seen = set()
        active = None
        for used, bssid, ssid, signal, security in info['aps']:
            if not ssid or bssid in seen:
                continue
            seen.add(bssid)
            suffix = f'{signal}% · ' + ('secured' if security and security != '--' else 'open')
            if used == '*' and len(info['wifi']) == 1:
                suffix = 'connected' if info['wifi'][0][2].startswith('connected') else 'connecting'
            self.networks.append(bssid, f'{ssid} — {suffix}')
            if used == '*':
                active = bssid
        self.networks.set_active_id(selected if selected in seen else (active or ''))
        if self.networks.get_active() < 0 and seen:
            self.networks.set_active(0)
        selected = self.saved.get_active_id()
        self.saved.remove_all()
        for uuid, name, kind, active in info['profiles']:
            self.saved.append(uuid, name)
        self.saved.set_active_id(selected or '')
        if self.saved.get_active() < 0 and info['profiles']:
            self.saved.set_active(0)
        self.sensitivity()
        # Do not leave an old "Connected" confirmation over a new disconnected state.
        if old != text and not self.busy and self.app.status.get_text() == self.last_message:
            self.app.feedback.hide()

    def sensitivity(self):
        if not self.ready or not self.info:
            return
        available = bool(self.info['wifi'])
        enabled = available and self.info['radio'] and any(row[2] not in ('unavailable', 'unmanaged') for row in self.info['wifi'])
        active = any(row[2].startswith(('connected', 'connecting')) for row in self.info['wifi'])
        self.radio.set_sensitive(available)
        self.disconnect.set_sensitive(enabled and active)
        self.networks.set_sensitive(enabled)
        self.password.set_sensitive(enabled)
        self.scan.set_sensitive(enabled)
        selected = self.networks.get_active_id()
        connected = {row[1] for row in self.info['aps'] if row[0] == '*'}
        self.connect.set_sensitive(enabled and bool(selected) and selected not in connected)
        selected = self.saved.get_active_id()
        connected = {row[0] for row in self.info['profiles'] if row[3] == 'yes'}
        self.saved.set_sensitive(enabled and bool(self.info['profiles']))
        self.saved_connect.set_sensitive(enabled and bool(selected) and selected not in connected)

    def operation(self, action, progress, confirmation):
        def prepare():
            self.busy = True
            self.revision += 1
            def job():
                error = None
                try:
                    action()
                except Exception as failure:
                    error = failure
                try:
                    info = snapshot()
                except Exception as failure:
                    info = None
                    error = error or RuntimeError('Could not refresh network status. Use Refresh status to try again.')
                message = self.app.error_text(error) if error else confirmation(info)
                self.last_message = message
                GLib.idle_add(self.finished, info)
                if error:
                    raise RuntimeError(message)
                return message
            return job
        self.app.perform(prepare, pending=progress)

    def finished(self, info):
        self.busy = False
        if self.closed:
            return
        if info is not None:
            self.update(info)
        else:
            self.status.set_text('Current Wi-Fi status is unavailable. Refresh status to try again.')
        if self.refresh_again:
            self.refresh_again = False
            self.schedule_refresh()

    def toggle_radio(self, *_):
        enabled = not self.info['radio']
        self.operation(lambda: backend.run('nmcli', 'radio', 'wifi', 'on' if enabled else 'off'),
                       'Turning Wi-Fi on…' if enabled else 'Turning Wi-Fi off…', summary)

    def scan_networks(self, *_):
        self.operation(lambda: backend.run('nmcli', '--wait', '20', '-f', 'SSID', 'device', 'wifi', 'list', '--rescan', 'yes', timeout=30),
                       'Scanning for Wi-Fi networks…',
                       lambda info: 'Scan complete. Select a network to connect.' if info['aps'] else 'No visible networks found. Try scanning again or check Wi-Fi range.')

    def connect_network(self, *_):
        selected = self.networks.get_active_id()
        if not selected:
            self.app.report('Scan for networks and select one first.', error=True)
            return
        ssid = next(row[2] for row in self.info['aps'] if row[1] == selected)
        secret = self.password.get_text()
        self.password.set_text('')
        if '\n' in secret or '\r' in secret:
            self.app.report('Password must be a single line.', error=True)
            return
        def connect():
            # Secret on stdin, never on the command line or in ErdOS preferences.
            try:
                backend.run('nmcli', '--ask', '--wait', '30', 'device', 'wifi', 'connect', selected,
                            input=secret+'\n', timeout=40)
            except Exception as error:
                message = self.app.error_text(error)
                if 'Secrets were required' in message:
                    message = 'The network needs a valid password. Check it and try again.'
                raise RuntimeError(f'Could not connect to “{ssid}”. {message}') from error
        self.operation(connect, f'Connecting to “{ssid}”…', summary)

    def connect_saved(self, *_):
        selected = self.saved.get_active_id()
        if not selected:
            self.app.report('Select a saved Wi-Fi connection first.', error=True)
            return
        name = next(row[1] for row in self.info['profiles'] if row[0] == selected)
        self.operation(lambda: backend.run('nmcli', '--wait', '30', 'connection', 'up', 'uuid', selected, timeout=40),
                       f'Connecting to “{name}”…', summary)

    def disconnect_wifi(self, *_):
        devices = [row[0] for row in self.info['wifi'] if row[2].startswith(('connected', 'connecting'))]
        self.operation(lambda: backend.run('nmcli', '--wait', '20', 'device', 'disconnect', *devices, timeout=30),
                       'Disconnecting Wi-Fi…', summary)

    def got_bus(self, _source, result):
        if self.closed:
            return
        try:
            self.bus = Gio.bus_get_finish(result)
            self.subscription = self.bus.signal_subscribe('org.freedesktop.NetworkManager',
                'org.freedesktop.DBus.Properties', 'PropertiesChanged', None, None,
                Gio.DBusSignalFlags.NONE, self.changed)
        except GLib.Error:
            pass  # Manual actions/Refresh status still fetch fresh state through nmcli.

    def changed(self, _bus, _sender, _path, _interface, _signal, parameters):
        interface, changed, invalidated = parameters.unpack()
        relevant = {'State', 'Connectivity', 'WirelessEnabled', 'Devices', 'ActiveConnections',
                    'ActiveConnection', 'ActiveAccessPoint', 'AccessPoints', 'Connections'}
        if interface.startswith('org.freedesktop.NetworkManager') and relevant.intersection(set(changed) | set(invalidated)):
            self.schedule_refresh()

    def tab_changed(self, *_):
        self.schedule_refresh()

    def schedule_refresh(self):
        if self.closed or not self.ready or self.app.stack.get_visible_child_name() != 'Network' or self.timer:
            return
        if self.busy or self.refreshing:
            self.refresh_again = True
            return
        self.timer = GLib.timeout_add(150, self.refresh)

    def refresh(self):
        self.timer = None
        if self.closed:
            return False
        if self.busy or self.refreshing:
            self.refresh_again = True
            return False
        self.refreshing = True
        revision = self.revision
        def worker():
            try:
                info = snapshot()
            except Exception:
                info = None
            GLib.idle_add(finish, info)
        def finish(info):
            self.refreshing = False
            if self.closed:
                return
            if revision != self.revision:
                self.schedule_refresh()
                return
            if info is not None:
                self.update(info)
            else:
                self.status.set_text('Current Wi-Fi status is unavailable. Refresh status to try again.')
            if self.refresh_again:
                self.refresh_again = False
                self.schedule_refresh()
        threading.Thread(target=worker, daemon=True).start()
        return False

    def close(self, *_):
        self.closed = True
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = None
        if self.bus and self.subscription:
            self.bus.signal_unsubscribe(self.subscription)
