# SPDX-License-Identifier: MIT
"""BlueZ page and pairing agent; asynchronous D-Bus, no resident UI service."""
from gi.repository import Gio, GLib, Gtk

ADAPTER = 'org.bluez.Adapter1'
DEVICE = 'org.bluez.Device1'
PROPERTIES = 'org.freedesktop.DBus.Properties'
AGENT_PATH = '/org/erdos/Settings/Agent'
AGENT_XML = '''<node><interface name="org.bluez.Agent1">
<method name="Release"/><method name="Cancel"/>
<method name="RequestPinCode"><arg type="o" direction="in"/><arg type="s" direction="out"/></method>
<method name="RequestPasskey"><arg type="o" direction="in"/><arg type="u" direction="out"/></method>
<method name="DisplayPinCode"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
<method name="DisplayPasskey"><arg type="o" direction="in"/><arg type="u" direction="in"/><arg type="q" direction="in"/></method>
<method name="RequestConfirmation"><arg type="o" direction="in"/><arg type="u" direction="in"/></method>
<method name="RequestAuthorization"><arg type="o" direction="in"/></method>
<method name="AuthorizeService"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
</interface></node>'''


class Bluetooth:
    def __init__(self, app, page):
        self.app, self.page = app, page
        self.bus = None
        self.owner = None
        self.closed = False
        self.objects = {}
        self.scanning = None
        self.pairing = None
        self.dialog = None
        self.pending = None
        self.timer = None
        self.refresh_pending = False
        self.loading = False
        self.agent_ready = False
        self.busy = False
        self.summary = app.note(page, 'Looking for Bluetooth adapters…')
        self.adapters = app.choice(page, 'Adapter', [])
        self.adapters.connect('changed', lambda *_: self.render_devices())
        self.controls = Gtk.Box(spacing=8)
        page.pack_start(self.controls, False, False, 0)
        self.power = self.button(self.controls, 'Turn on', self.toggle_power)
        self.scan = self.button(self.controls, 'Scan for devices', self.toggle_scan)
        self.button(self.controls, 'Refresh', self.refresh)
        self.devices = app.choice(page, 'Device', [])
        self.details = app.note(page, '')
        self.devices.connect('changed', lambda *_: self.render_state())
        self.actions = Gtk.Box(spacing=8)
        page.pack_start(self.actions, False, False, 0)
        self.pair_button = self.button(self.actions, 'Pair & connect', self.pair)
        self.connect_button = self.button(self.actions, 'Connect', self.connect_device)
        self.trust_button = self.button(self.actions, 'Trust', self.trust)
        self.button(self.actions, 'Forget', self.forget)
        app.note(page, 'Put your device in pairing mode, then scan. Trust allows future connections without asking again. Scanning stops after 30 seconds or when you leave this tab. If power is blocked, check the laptop’s wireless switch or airplane mode.')
        app.window.connect('destroy', self.close)
        app.stack.connect('notify::visible-child-name', self.tab_changed)
        self.render_state()
        Gio.bus_get(Gio.BusType.SYSTEM, None, self.got_bus)

    def button(self, box, label, action):
        button = Gtk.Button(label=label)
        button.connect('clicked', lambda *_: action())
        box.pack_start(button, False, False, 0)
        return button

    def got_bus(self, _source, result):
        if self.closed:
            return
        try:
            self.bus = Gio.bus_get_finish(result)
            info = Gio.DBusNodeInfo.new_for_xml(AGENT_XML).interfaces[0]
            self.registration = self.bus.register_object(AGENT_PATH, info, self.agent, None, None)
            self.subscription = self.bus.signal_subscribe('org.bluez', None, None, None, None,
                Gio.DBusSignalFlags.NONE, self.changed)
            self.watch = Gio.bus_watch_name_on_connection(self.bus, 'org.bluez',
                Gio.BusNameWatcherFlags.AUTO_START, self.appeared, self.vanished)
        except GLib.Error as error:
            self.summary.set_text(f'Bluetooth unavailable: {error.message}')

    def appeared(self, _bus, _name, owner):
        self.owner = owner
        self.call('/org/bluez', 'org.bluez.AgentManager1', 'RegisterAgent',
                  GLib.Variant('(os)', (AGENT_PATH, 'KeyboardDisplay')), self.registered)
        self.refresh()

    def registered(self, _reply):
        self.agent_ready = True
        self.render_state()

    def vanished(self, *_):
        self.owner = None
        self.agent_ready = False
        self.objects = {}
        self.scanning = None
        self.cancel_dialog()
        self.render()
        self.summary.set_text('Bluetooth service unavailable. Check that BlueZ is installed and bluetooth.service is running.')

    def call(self, path, interface, method, parameters=None, done=None, failed=None):
        if self.closed or not self.bus or not self.owner:
            return
        def finish(bus, result):
            try:
                reply = bus.call_finish(result)
                if not self.closed and done:
                    done(reply.unpack())
            except GLib.Error as error:
                if not self.closed:
                    if failed:
                        failed(error)
                    else:
                        self.app.report(self.app.error_text(error), error=True)
        self.bus.call(self.owner, path, interface, method, parameters, None,
                      Gio.DBusCallFlags.NONE, 120000 if method == 'Pair' else 20000,
                      None, finish)

    def changed(self, _bus, _sender, _path, interface, signal, _args):
        if interface == 'org.freedesktop.DBus.ObjectManager' or (interface == PROPERTIES and signal == 'PropertiesChanged'):
            if not self.refresh_pending and not self.closed:
                self.refresh_pending = True
                GLib.idle_add(self.refresh)

    def refresh(self):
        self.refresh_pending = False
        if self.loading or self.closed or not self.owner:
            return False
        self.loading = True
        def loaded(reply):
            self.loading = False
            self.objects = reply[0]
            self.render()
        def failed(error):
            self.loading = False
            self.summary.set_text(error.message)
        self.call('/', 'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects', done=loaded, failed=failed)
        return False

    def render(self):
        selected = self.adapters.get_active_id()
        self.adapters.remove_all()
        for path, interfaces in sorted(self.objects.items()):
            if ADAPTER in interfaces:
                props = interfaces[ADAPTER]
                self.adapters.append(path, f"{props.get('Alias', 'Bluetooth')} — {props.get('Address', '')}")
        if selected:
            self.adapters.set_active_id(selected)
        if self.adapters.get_active() < 0:
            self.adapters.set_active(0)
        self.render_devices()

    def render_devices(self):
        selected = self.devices.get_active_id()
        adapter = self.adapters.get_active_id()
        self.devices.remove_all()
        for path, interfaces in sorted(self.objects.items()):
            props = interfaces.get(DEVICE, {})
            if props.get('Adapter') == adapter:
                label = props.get('Alias', props.get('Address', path))
                state = 'connected' if props.get('Connected') else ('paired' if props.get('Paired') else 'available')
                self.devices.append(path, f'{label} — {state}')
        if selected:
            self.devices.set_active_id(selected)
        if self.devices.get_active() < 0:
            self.devices.set_active(0)
        self.render_state()

    def render_state(self):
        adapter = self.objects.get(self.adapters.get_active_id(), {}).get(ADAPTER, {})
        device = self.objects.get(self.devices.get_active_id(), {}).get(DEVICE, {})
        powered = adapter.get('Powered', False)
        self.summary.set_text('No Bluetooth adapter detected. Connect an adapter to use Bluetooth.' if not adapter else ('Bluetooth is on.' if powered else 'Bluetooth is off.'))
        self.controls.set_sensitive(bool(adapter) and not self.busy)
        self.adapters.set_sensitive(not self.busy)
        self.devices.set_sensitive(not self.busy)
        self.actions.set_sensitive(bool(device) and powered and not self.busy)
        self.power.set_label('Turn off' if powered else 'Turn on')
        self.scan.set_label('Stop scanning' if self.scanning else 'Scan for devices')
        self.scan.set_sensitive(powered)
        self.pair_button.set_sensitive(not device.get('Paired', False) and self.agent_ready)
        self.connect_button.set_label('Disconnect' if device.get('Connected') else 'Connect')
        self.connect_button.set_sensitive(device.get('Paired', False))
        self.trust_button.set_label('Untrust' if device.get('Trusted') else 'Trust')
        self.trust_button.set_sensitive(device.get('Paired', False))
        self.details.set_text(f"{device.get('Address', '')}  {'Trusted' if device.get('Trusted') else 'Not trusted'}" if device else ('No devices found. Turn on Bluetooth and scan.' if adapter else ''))

    def operation(self, path, interface, method, parameters=None, done=None):
        self.busy = True
        self.render_state()
        self.app.report('Working…')
        def finish(reply=None, error=None):
            self.busy = False
            self.app.report(self.app.error_text(error) if error else 'Bluetooth updated.', error=bool(error))
            self.render_state()
            self.refresh()
            if not error and done:
                done(reply)
        self.call(path, interface, method, parameters,
                  lambda reply: finish(reply), lambda error: finish(error=error))

    def set_property(self, path, interface, name, value):
        self.operation(path, PROPERTIES, 'Set', GLib.Variant('(ssv)', (interface, name, GLib.Variant('b', value))))

    def toggle_power(self):
        path = self.adapters.get_active_id()
        self.set_property(path, ADAPTER, 'Powered', not self.objects[path][ADAPTER]['Powered'])

    def toggle_scan(self):
        if self.scanning:
            self.stop_scan(); return
        path = self.adapters.get_active_id()
        def started(_reply):
            self.scanning = path
            if self.app.stack.get_visible_child_name() != 'Bluetooth':
                self.stop_scan(); return
            self.timer = GLib.timeout_add_seconds(30, self.stop_scan)
            self.render_state()
        self.operation(path, ADAPTER, 'StartDiscovery', done=started)

    def stop_scan(self):
        if self.timer:
            GLib.source_remove(self.timer); self.timer = None
        path, self.scanning = self.scanning, None
        if path:
            self.call(path, ADAPTER, 'StopDiscovery', done=lambda _: self.refresh())
        if not self.closed:
            self.render_state()
        return False

    def tab_changed(self, *_):
        if self.app.stack.get_visible_child_name() != 'Bluetooth':
            self.stop_scan()

    def pair(self):
        self.pairing = self.devices.get_active_id()
        path = self.pairing
        self.busy = True; self.render_state()
        self.app.report('Pairing… Follow any confirmation or PIN prompt.')
        def finish(reply=None, error=None):
            self.pairing = None
            self.cancel_dialog()
            self.busy = False
            self.render_state(); self.refresh()
            if error:
                self.app.report(self.app.error_text(error), error=True)
            else:
                self.operation(path, DEVICE, 'Connect')
        self.call(path, DEVICE, 'Pair', done=lambda reply: finish(reply), failed=lambda error: finish(error=error))

    def connect_device(self):
        path = self.devices.get_active_id()
        self.operation(path, DEVICE, 'Disconnect' if self.objects[path][DEVICE].get('Connected') else 'Connect')

    def trust(self):
        path = self.devices.get_active_id()
        self.set_property(path, DEVICE, 'Trusted', not self.objects[path][DEVICE].get('Trusted', False))

    def forget(self):
        path = self.devices.get_active_id()
        adapter = self.objects[path][DEVICE]['Adapter']
        dialog = Gtk.MessageDialog(transient_for=self.app.window, modal=True,
            message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.YES_NO,
            text='Forget this Bluetooth device?')
        dialog.format_secondary_text('Its pairing information will be removed. Pair again to reconnect.')
        dialog.set_default_response(Gtk.ResponseType.NO)
        def response(widget, answer):
            widget.destroy()
            if answer == Gtk.ResponseType.YES and not self.closed:
                self.operation(adapter, ADAPTER, 'RemoveDevice', GLib.Variant('(o)', (path,)))
        dialog.connect('response', response)
        dialog.set_destroy_with_parent(True)
        dialog.show_all()

    def cancel_dialog(self):
        pending, self.pending = self.pending, None
        if pending:
            pending.return_dbus_error('org.bluez.Error.Canceled', 'Pairing canceled')
        if self.dialog:
            dialog, self.dialog = self.dialog, None
            dialog.destroy()

    def agent(self, _bus, sender, _path, _interface, method, parameters, invocation):
        if sender != self.owner or self.closed:
            invocation.return_dbus_error('org.bluez.Error.Rejected', 'Unauthorized agent caller'); return
        args = parameters.unpack()
        if method in ('Release', 'Cancel'):
            self.cancel_dialog()
            if method == 'Release':
                self.agent_ready = False
            invocation.return_value(None); return
        if not self.pairing or not args or args[0] != self.pairing:
            invocation.return_dbus_error('org.bluez.Error.Rejected', 'No user-initiated pairing'); return
        self.cancel_dialog()
        name = self.objects.get(args[0], {}).get(DEVICE, {}).get('Alias', 'Bluetooth device')
        display = method in ('DisplayPinCode', 'DisplayPasskey')
        entry_method = method in ('RequestPinCode', 'RequestPasskey')
        text = f'Pair with {name}?'
        if method in ('RequestConfirmation', 'DisplayPasskey'):
            text = f'{name}: {args[1]:06d}\n' + ('Type this code on the Bluetooth keyboard, then press Enter.' if display else 'Does this code match the other device?')
        elif method == 'DisplayPinCode':
            text = f'{name}: {args[1]}\nType this code on the Bluetooth keyboard, then press Enter.'
        elif entry_method:
            text = f'Enter the {"numeric passkey" if method == "RequestPasskey" else "PIN"} for {name}.'
        elif method == 'AuthorizeService':
            text = f'Allow {name} to use service {args[1]}?'
        dialog = Gtk.Dialog(title='Bluetooth pairing', transient_for=self.app.window, modal=True)
        self.dialog = dialog
        dialog.add_button('Cancel', Gtk.ResponseType.CANCEL)
        if not display:
            dialog.add_button('Confirm', Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        label = Gtk.Label(label=text, wrap=True); label.set_max_width_chars(55); label.set_margin_start(16); label.set_margin_end(16)
        dialog.get_content_area().pack_start(label, True, True, 16)
        entry = Gtk.Entry() if entry_method else None
        if entry:
            entry.set_max_length(6 if method == 'RequestPasskey' else 16)
            dialog.get_content_area().pack_start(entry, False, False, 8)
        if display:
            invocation.return_value(None)
        else:
            self.pending = invocation
        def response(_dialog, answer):
            if answer == Gtk.ResponseType.OK and entry:
                value = entry.get_text()
                if not value or (method == 'RequestPasskey' and (not value.isascii() or not value.isdigit())):
                    label.set_text('Enter a valid ' + ('0–999999 passkey.' if method == 'RequestPasskey' else '1–16 character PIN.')); return
            pending, self.pending = self.pending, None
            if pending:
                if answer != Gtk.ResponseType.OK:
                    pending.return_dbus_error('org.bluez.Error.Rejected', 'Pairing rejected by user')
                elif method == 'RequestPinCode':
                    pending.return_value(GLib.Variant('(s)', (entry.get_text(),)))
                elif method == 'RequestPasskey':
                    pending.return_value(GLib.Variant('(u)', (int(entry.get_text()),)))
                else:
                    pending.return_value(None)
            if answer != Gtk.ResponseType.OK and self.pairing:
                self.call(self.pairing, DEVICE, 'CancelPairing')
            self.dialog = None
            dialog.destroy()
        dialog.connect('response', response)
        dialog.show_all()

    def close(self, *_):
        self.stop_scan()
        if self.pairing:
            self.call(self.pairing, DEVICE, 'CancelPairing')
        self.cancel_dialog()
        if self.agent_ready:
            self.call('/org/bluez', 'org.bluez.AgentManager1', 'UnregisterAgent', GLib.Variant('(o)', (AGENT_PATH,)))
        self.closed = True
        if self.bus:
            if hasattr(self, 'watch'):
                Gio.bus_unwatch_name(self.watch)
            if hasattr(self, 'subscription'):
                self.bus.signal_unsubscribe(self.subscription)
            if hasattr(self, 'registration'):
                self.bus.unregister_object(self.registration)
