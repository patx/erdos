# SPDX-License-Identifier: MIT
"""Network controls with current state, explicit actions and event-driven refresh."""
import ipaddress
from pathlib import Path
import tempfile
import threading
import uuid
from gi.repository import Gio, GLib, Gtk
import settings as backend


def snapshot():
    devices = backend.nm_lines('-f', 'DEVICE,TYPE,STATE,CONNECTION', 'device', 'status')
    wifi = [row for row in devices if row[1] == 'wifi']
    radio = backend.run('nmcli', 'radio', 'wifi') == 'enabled'
    connections = backend.nm_lines('-f', 'UUID,NAME,TYPE,ACTIVE', 'connection', 'show')
    profiles = [row for row in connections if row[2] in ('wifi', '802-11-wireless')]
    aps = backend.nm_lines('-f', 'IN-USE,BSSID,SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list', '--rescan', 'no') if wifi and radio else []
    return dict(devices=devices, wifi=wifi, radio=radio, profiles=profiles, aps=aps,
                connections=[row for row in connections if row[2] in ('wifi', '802-11-wireless', 'ethernet', '802-3-ethernet')],
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


def set_ipv4(profile, address, gateway, dns):
    address, gateway = address.strip(), gateway.strip()
    if address and '/' not in address:
        raise ValueError('Include a prefix length in the IPv4 address, such as /24.')
    if gateway and not address:
        raise ValueError('Set a static IPv4 address to specify a gateway.')
    ip = str(ipaddress.IPv4Interface(address)) if address else ''
    router = str(ipaddress.IPv4Address(gateway)) if gateway else ''
    servers = ','.join(str(ipaddress.IPv4Address(server.strip())) for server in dns.split(',') if server.strip())
    backend.run('nmcli', 'connection', 'modify', 'uuid', profile,
                'ipv4.method', 'manual' if ip else 'auto', 'ipv4.addresses', ip,
                'ipv4.gateway', router, 'ipv4.dns', servers,
                'ipv4.ignore-auto-dns', 'yes' if servers else 'no')


def activate_enterprise(profile, password):
    if not password or any(char in password for char in ('\0', '\r', '\n')):
        raise ValueError('Enter a single-line enterprise Wi-Fi password.')
    with tempfile.NamedTemporaryFile(mode='w', prefix='erdos-wifi-') as credentials:
        credentials.write(f'802-1x.password:{password}\n')
        credentials.flush()
        backend.run('nmcli', '--wait', '30', 'connection', 'up', 'uuid', profile,
                    'passwd-file', credentials.name, timeout=40)


def connect_enterprise(ssid, identity, domain, certificate, password):
    if not all((ssid, identity, domain, certificate, password)) or any(
            char in password for char in ('\0', '\r', '\n')):
        raise ValueError('Enter the network, identity, server domain, CA certificate, and a single-line password.')
    cert = Path(certificate).expanduser()
    if not cert.is_file():
        raise ValueError('Choose a readable CA certificate file.')
    profile = str(uuid.uuid4())
    backend.run('nmcli', 'connection', 'add', 'type', 'wifi', 'ifname', '*',
                'con-name', ssid, 'ssid', ssid, 'connection.uuid', profile,
                'connection.autoconnect', 'no', 'wifi-sec.key-mgmt', 'wpa-eap',
                '802-1x.eap', 'peap', '802-1x.phase2-auth', 'mschapv2',
                '802-1x.identity', identity, '802-1x.ca-cert', str(cert.resolve()),
                '802-1x.domain-suffix-match', domain, '802-1x.password-flags', '2')
    try:
        activate_enterprise(profile, password)
    except Exception as error:
        try:
            backend.run('nmcli', 'connection', 'delete', 'uuid', profile)
        except Exception as cleanup:
            raise RuntimeError(f'{error} Could not remove the incomplete profile: {cleanup}') from error
        raise


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
        self.password.connect('activate', lambda *_: self.connect_network() if self.connect.get_sensitive() else None)
        self.saved = self.app.choice(page, 'Saved Wi-Fi connection', [])
        self.saved_connect = Gtk.Button(label='Connect saved network', halign=Gtk.Align.START)
        self.saved_connect.connect('clicked', self.connect_saved)
        page.pack_start(self.saved_connect, False, False, 0)
        self.networks.connect('changed', lambda *_: self.sensitivity())
        self.saved.connect('changed', lambda *_: self.sensitivity())
        button = Gtk.Button(label='Refresh status', halign=Gtk.Align.START)
        button.connect('clicked', lambda *_: self.operation(lambda: None, 'Refreshing network status…', lambda info: 'Network status refreshed.'))
        page.pack_start(button, False, False, 0)
        self.advanced = self.app.choice(page, 'Network profile', [])
        self.ipv4 = Gtk.Button(label='Edit IPv4 and DNS', halign=Gtk.Align.START)
        self.ipv4.connect('clicked', self.edit_ipv4)
        page.pack_start(self.ipv4, False, False, 0)
        self.enterprise = Gtk.Button(label='Connect to enterprise Wi-Fi', halign=Gtk.Align.START)
        self.enterprise.connect('clicked', self.enterprise_wifi)
        page.pack_start(self.enterprise, False, False, 0)
        self.app.note(page, 'Enterprise Wi-Fi supports PEAP with MSCHAPv2. Use the CA certificate and server domain supplied by your network administrator. Enter your password again when reconnecting to a saved enterprise network.')
        self.profile_status = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        page.pack_start(self.profile_status, False, False, 0)
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
        selected = self.advanced.get_active_id()
        self.advanced.remove_all()
        for profile, name, _, _ in info['connections']:
            self.advanced.append(profile, name)
        if not selected or not self.advanced.set_active_id(selected):
            self.advanced.set_active(0)
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
        self.advanced.set_sensitive(bool(self.info['connections']))
        self.ipv4.set_sensitive(bool(self.info['connections']))
        self.enterprise.set_sensitive(enabled)

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
        password = self.password.get_text()
        self.password.set_text('')

        def connect():
            if password:
                security = backend.run('nmcli', '-g', '802-11-wireless-security.key-mgmt',
                                       'connection', 'show', 'uuid', selected)
                if security in ('wpa-eap', 'wpa-eap-suite-b-192'):
                    activate_enterprise(selected, password)
                    return
            backend.run('nmcli', '--wait', '30', 'connection', 'up', 'uuid', selected, timeout=40)

        self.operation(connect, f'Connecting to “{name}”…', summary)

    def edit_ipv4(self, *_):
        profile = self.advanced.get_active_id()
        if not profile:
            return
        def fetch():
            return [backend.run('nmcli', '-g', key, 'connection', 'show', 'uuid', profile)
                    for key in ('ipv4.method', 'ipv4.addresses', 'ipv4.gateway', 'ipv4.dns')]

        def edit(_box, values):
            method, address, gateway, dns = values
            if (method not in ('auto', 'manual') or (method == 'auto' and address)
                    or ',' in address or '\n' in address):
                self.app.report('This profile needs advanced IPv4 settings. Manage it with nmcli.', error=True)
                return
            def save(fields):
                self.operation(lambda: set_ipv4(profile, *fields), 'Saving network profile…',
                               lambda _: 'Profile saved. Reconnect to use the new settings.')
            self.app.edit_fields('IPv4 and DNS', [
                ('Static IPv4 address with prefix (blank for DHCP)', address),
                ('IPv4 gateway', gateway),
                ('DNS servers (comma-separated)', dns.replace('\n', ',')),
            ], save)

        box = self.profile_status
        for child in box.get_children():
            child.destroy()
        box.show()
        self.app.load_section(box, fetch, edit)

    def enterprise_wifi(self, *_):
        dialog = Gtk.Dialog(title='Enterprise Wi-Fi (PEAP)', transient_for=self.app.window, modal=True)
        dialog.add_buttons('Cancel', Gtk.ResponseType.CANCEL, 'Connect', Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        box.set_border_width(12)
        ssid = self.app.row(box, 'Network name (SSID)', Gtk.Entry())
        identity = self.app.row(box, 'Identity', Gtk.Entry())
        domain = self.app.row(box, 'Server domain', Gtk.Entry())
        certificate = self.app.row(box, 'CA certificate', Gtk.FileChooserButton(
            title='Choose a CA certificate', action=Gtk.FileChooserAction.OPEN))
        password = self.app.row(box, 'Password', Gtk.Entry(visibility=False, input_purpose=Gtk.InputPurpose.PASSWORD))
        dialog.show_all()
        if dialog.run() == Gtk.ResponseType.OK:
            values = (ssid.get_text(), identity.get_text(), domain.get_text(), certificate.get_filename(), password.get_text())
            dialog.destroy()
            self.operation(lambda: connect_enterprise(*values), 'Connecting to enterprise Wi-Fi…', summary)
        else:
            dialog.destroy()

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
