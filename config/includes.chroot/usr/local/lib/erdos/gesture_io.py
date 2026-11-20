"""Direct libinput and X11 I/O for ErdOS, using libraries already in the image."""
import ctypes as C
import errno
import os
import socket
import subprocess
import time

I, U, L, V = C.c_int, C.c_ulong, C.c_long, C.c_void_p


def bind(library, name, result, *arguments):
    function = getattr(library, name)
    function.restype, function.argtypes = result, list(arguments)
    return function


class KeyEvent(C.Structure):
    _fields_ = [('type', I), ('serial', U), ('send_event', I), ('display', V),
                ('window', U), ('root', U), ('subwindow', U), ('time', U),
                ('x', I), ('y', I), ('x_root', I), ('y_root', I),
                ('state', C.c_uint), ('keycode', C.c_uint), ('same_screen', I)]


class Message(C.Structure):
    _fields_ = [('type', I), ('serial', U), ('send_event', I), ('display', V),
                ('window', U), ('message_type', U), ('format', I), ('data', L * 5)]


class PropertyEvent(C.Structure):
    _fields_ = [('type', I), ('serial', U), ('send_event', I), ('display', V),
                ('window', U), ('atom', U), ('time', U), ('state', I)]


class Cookie(C.Structure):
    _fields_ = [('type', I), ('serial', U), ('send_event', I), ('display', V),
                ('extension', I), ('evtype', I), ('cookie', C.c_uint), ('data', V)]


class RawKey(C.Structure):
    _fields_ = [('type', I), ('serial', U), ('send_event', I), ('display', V),
                ('extension', I), ('evtype', I), ('time', U), ('deviceid', I),
                ('sourceid', I), ('detail', I), ('flags', I)]


class InputMask(C.Structure):
    _fields_ = [('deviceid', I), ('mask_len', I), ('mask', C.POINTER(C.c_ubyte))]


class Event(C.Union):
    _fields_ = [('type', I), ('key', KeyEvent), ('message', Message), ('property', PropertyEvent), ('cookie', Cookie), ('pad', L * 24)]


class Attributes(C.Structure):
    _fields_ = [(name, I) for name in ('x', 'y', 'width', 'height', 'border_width', 'depth')]
    _fields_ += [('visual', V), ('root', U)]
    _fields_ += [(name, I) for name in ('class_', 'bit_gravity', 'win_gravity', 'backing_store')]
    _fields_ += [('backing_planes', U), ('backing_pixel', U), ('save_under', I), ('colormap', U),
                 ('map_installed', I), ('map_state', I), ('all_event_masks', L),
                 ('your_event_mask', L), ('do_not_propagate_mask', L),
                 ('override_redirect', I), ('screen', V)]


class ClassHint(C.Structure):
    _fields_ = [('res_name', V), ('res_class', V)]


class Desktop:
    def __init__(self, log_path):
        self.x = C.CDLL('libX11.so.6')
        signatures = {
            'XOpenDisplay': (V, C.c_char_p), 'XDefaultRootWindow': (U, V),
            'XConnectionNumber': (I, V), 'XCloseDisplay': (I, V),
            'XInternAtom': (U, V, C.c_char_p, I), 'XFlush': (I, V),
            'XQueryTree': (I, V, U, C.POINTER(U), C.POINTER(U), C.POINTER(C.POINTER(U)), C.POINTER(C.c_uint)),
            'XGetWindowAttributes': (I, V, U, C.POINTER(Attributes)),
            'XFetchName': (I, V, U, C.POINTER(V)), 'XFree': (I, V),
            'XGetClassHint': (I, V, U, C.POINTER(ClassHint)),
            'XGetWindowProperty': (I, V, U, U, L, L, I, U, C.POINTER(U), C.POINTER(I), C.POINTER(U), C.POINTER(U), C.POINTER(V)),
            'XSendEvent': (I, V, U, I, L, C.POINTER(Event)),
            'XStringToKeysym': (U, C.c_char_p), 'XKeysymToKeycode': (C.c_ubyte, V, U),
            'XQueryKeymap': (I, V, V), 'XPending': (I, V),
            'XSelectInput': (I, V, U, L),
            'XGetEventData': (I, V, C.POINTER(Cookie)), 'XFreeEventData': (None, V, C.POINTER(Cookie)),
            'XNextEvent': (I, V, C.POINTER(Event)), 'XRefreshKeyboardMapping': (I, V),
        }
        for name, types in signatures.items():
            bind(self.x, name, *types)
        # An overview can disappear between a query and a key event.
        self.error_handler = C.CFUNCTYPE(I, V, V)(lambda *_: 0)
        bind(self.x, 'XSetErrorHandler', V, V)(self.error_handler)
        self.display = self.x.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError('Cannot connect to the desktop X server.')
        self.root = self.x.XDefaultRootWindow(self.display)
        self.fd = self.x.XConnectionNumber(self.display)
        self.connection = socket.fromfd(self.fd, socket.AF_UNIX, socket.SOCK_STREAM)
        self.alive = True
        self.atoms = {}
        self.log_path = log_path
        self.overview_child = None
        self.randr_event = None
        self.manage_workspaces = False
        self.session_active = True
        self.super_enabled = False
        self.super_candidate = None
        self.pressed = set()
        self.clients = set()
        self.xtest = C.CDLL('libXtst.so.6')
        bind(self.xtest, 'XTestFakeKeyEvent', I, V, C.c_uint, I, U)

    def atom(self, name):
        if name not in self.atoms:
            self.atoms[name] = self.x.XInternAtom(self.display, name.encode(), 0)
        return self.atoms[name]

    def pump(self):
        try:
            if not self.connection.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT):
                self.alive = False
                return False
        except BlockingIOError:
            pass
        workspaces_changed = False
        displays_changed = False
        while self.x.XPending(self.display):
            event = Event()
            self.x.XNextEvent(self.display, C.byref(event))
            if self.randr_event is not None and event.type in (self.randr_event, self.randr_event + 1):
                displays_changed = True
            elif event.type == 34:  # MappingNotify
                self.x.XRefreshKeyboardMapping(C.byref(event))
                if self.manage_workspaces:
                    self.super_codes = {self.keycode('Super_L'), self.keycode('Super_R')}
            elif event.type == 35 and self.manage_workspaces:
                cookie = event.cookie
                if cookie.extension == self.xi_opcode and self.x.XGetEventData(self.display, C.byref(cookie)):
                    try:
                        raw = C.cast(cookie.data, C.POINTER(RawKey)).contents
                        self.super_event(raw.evtype, raw.detail)
                    finally:
                        self.x.XFreeEventData(self.display, C.byref(cookie))
            elif event.type == 28 and self.manage_workspaces:
                wanted = ('_NET_CLIENT_LIST', '_NET_CURRENT_DESKTOP', '_NET_NUMBER_OF_DESKTOPS') if event.property.window == self.root else ('_NET_WM_DESKTOP', '_NET_WM_WINDOW_TYPE')
                if event.property.atom in {self.atom(name) for name in wanted}:
                    workspaces_changed = True
        if workspaces_changed:
            self.sync_workspaces()
        if displays_changed:
            try:
                import settings
                prefs = settings.preferences()
                if prefs.get('background_image'):
                    settings.apply_background(prefs)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                print(f'Cannot refresh background: {error}', flush=True)
        return True

    def close(self):
        if self.alive:
            self.x.XCloseDisplay(self.display)
        else:
            os.close(self.fd)
        self.connection.close()

    def property(self, name, window=None):
        actual_type, count, remaining = U(), U(), U()
        fmt, pointer = I(), V()
        status = self.x.XGetWindowProperty(self.display, self.root if window is None else window, self.atom(name),
                                          0, 65536, 0, 0, C.byref(actual_type), C.byref(fmt),
                                          C.byref(count), C.byref(remaining), C.byref(pointer))
        try:
            if status == 0 and fmt.value == 32 and pointer.value:
                return list(C.cast(pointer, C.POINTER(U))[:count.value])
            return []
        finally:
            if pointer.value:
                self.x.XFree(pointer)

    def configure_session(self, preferences):
        self.dynamic = preferences.get('dynamic_workspaces', True)
        self.fixed_count = max(1, min(32, int(preferences.get('workspace_count', 2))))
        self.super_enabled = preferences.get('super_overview', True)
        self.super_candidate = None
        if not self.manage_workspaces:
            self.manage_workspaces = True
            self.randr = C.CDLL('libXrandr.so.2')
            event_base, error_base = I(), I()
            query = bind(self.randr, 'XRRQueryExtension', I, V, C.POINTER(I), C.POINTER(I))
            if query(self.display, C.byref(event_base), C.byref(error_base)):
                self.randr_event = event_base.value
                bind(self.randr, 'XRRSelectInput', None, V, U, I)(self.display, self.root, 1 | 2 | 4)
            self.x.XSelectInput(self.display, self.root, 1 << 22)
            self.super_codes = {self.keycode('Super_L'), self.keycode('Super_R')}
            self.xi = C.CDLL('libXi.so.6')
            major, minor = I(2), I(2)
            bind(self.xi, 'XIQueryVersion', I, V, C.POINTER(I), C.POINTER(I))(self.display, C.byref(major), C.byref(minor))
            opcode, first_event, first_error = I(), I(), I()
            bind(self.x, 'XQueryExtension', I, V, C.c_char_p, C.POINTER(I), C.POINTER(I), C.POINTER(I))(
                self.display, b'XInputExtension', C.byref(opcode), C.byref(first_event), C.byref(first_error))
            self.xi_opcode = opcode.value
            mask_bytes = (C.c_ubyte * 3)()
            for event in (13,14,15,16):
                mask_bytes[event // 8] |= 1 << (event % 8)
            mask = InputMask(1,3,mask_bytes)  # XIAllMasterDevices; observe, never grab keys.
            bind(self.xi, 'XISelectEvents', I, V, U, C.POINTER(InputMask), I)(self.display,self.root,C.byref(mask),1)
        self.sync_workspaces()

    def super_event(self, kind, code):
        if not self.session_active or not self.super_enabled:
            self.super_candidate = None
            self.pressed.clear()
            return
        if kind in (15,16):
            self.super_candidate = None
        elif kind == 13:
            if code in self.super_codes and code not in self.pressed and not self.pressed:
                mapping = (C.c_ubyte * 32)()
                self.x.XQueryKeymap(self.display, mapping)
                held = {key for key in range(256) if mapping[key//8] & (1 << (key%8))}
                self.super_candidate = code if not (held - {code}) else None
            elif code not in self.super_codes or code != self.super_candidate:
                self.super_candidate = None
            self.pressed.add(code)
        elif kind == 14:
            invoke = code == self.super_candidate
            self.super_candidate = None
            self.pressed.discard(code)
            if invoke:
                self.action('overview-show')

    def sync_workspaces(self):
        if not self.manage_workspaces:
            return
        clients = set(self.property('_NET_CLIENT_LIST'))
        for window in clients - self.clients:
            self.x.XSelectInput(self.display, window, (1 << 22) | (1 << 17))
        self.clients = clients
        current = self.property('_NET_CURRENT_DESKTOP') or [0]
        count = self.property('_NET_NUMBER_OF_DESKTOPS') or [2]
        last = current[0]
        ignored = {self.atom('_NET_WM_WINDOW_TYPE_DOCK'), self.atom('_NET_WM_WINDOW_TYPE_DESKTOP')}
        for window in clients:
            if ignored.intersection(self.property('_NET_WM_WINDOW_TYPE',window)):
                continue
            desktop = self.property('_NET_WM_DESKTOP',window)
            if desktop and desktop[0] < count[0]:  # Sticky windows use 0xffffffff.
                last = max(last,desktop[0])
        desired = min(1000, max(2,last+2) if self.dynamic else max(self.fixed_count,last+1))
        if desired != count[0]:
            event = Event()
            event.message = Message(type=33, display=self.display, window=self.root,
                message_type=self.atom('_NET_NUMBER_OF_DESKTOPS'), format=32)
            event.message.data[0] = desired
            self.x.XSendEvent(self.display,self.root,0,(1 << 19) | (1 << 20),C.byref(event))
        self.x.XFlush(self.display)

    def overview(self):
        root, parent, count, children = U(), U(), C.c_uint(), C.POINTER(U)()
        if not self.x.XQueryTree(self.display, self.root, C.byref(root), C.byref(parent),
                                 C.byref(children), C.byref(count)):
            return []
        matches = []
        try:
            for window in children[:count.value]:
                attributes = Attributes()
                if not self.x.XGetWindowAttributes(self.display, window, C.byref(attributes)) or attributes.map_state != 2:
                    continue
                name = V()
                if self.x.XFetchName(self.display, window, C.byref(name)) and name.value:
                    try:
                        if C.string_at(name) == b'skippy-xd fullscreen window':
                            hint = ClassHint()
                            if self.x.XGetClassHint(self.display, window, C.byref(hint)):
                                try:
                                    if hint.res_class and C.string_at(hint.res_class) == b'skippy-xd':
                                        matches.append(window)
                                finally:
                                    for pointer in (hint.res_name, hint.res_class):
                                        if pointer:
                                            self.x.XFree(pointer)
                    finally:
                        self.x.XFree(name)
        finally:
            if children:
                self.x.XFree(children)
        return matches

    def keycode(self, name):
        code = self.x.XKeysymToKeycode(self.display, self.x.XStringToKeysym(name.encode()))
        if not code:
            raise RuntimeError(f'No X11 keycode for {name}.')
        return code

    def hide(self):
        # A quick down-swipe may follow up before the overview finishes starting.
        if self.overview_child and self.overview_child.poll() is None and not self.overview():
            self.overview_child.terminate()
            try:
                self.overview_child.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.overview_child.kill()
                self.overview_child.wait()
        windows = self.overview()
        for window in windows:
            event = Event()
            event.key = KeyEvent(type=2, display=self.display, window=window,
                                 root=self.root, keycode=self.keycode('Escape'), same_screen=1)
            self.x.XSendEvent(self.display, window, 0, 1, C.byref(event))
            event.type = 3
            self.x.XSendEvent(self.display, window, 0, 2, C.byref(event))
        self.x.XFlush(self.display)
        if windows:
            until = time.monotonic() + 2
            while self.overview() and time.monotonic() < until:
                time.sleep(.01)
            if self.overview():
                raise RuntimeError('Overview did not close.')

    def cycle(self, direction):
        # Clear and restore held modifiers, as xdotool --clearmodifiers did.
        mapping = (C.c_ubyte * 32)()
        self.x.XQueryKeymap(self.display, mapping)
        modifiers = [self.keycode(key) for key in ('Shift_L', 'Shift_R', 'Control_L',
                     'Control_R', 'Alt_L', 'Alt_R', 'Super_L', 'Super_R')]
        held = {key for key in modifiers if mapping[key // 8] & (1 << (key % 8))}
        send = lambda code, down: self.xtest.XTestFakeKeyEvent(self.display, code, down, 0)
        for code in held:
            send(code, 0)
        keys = [self.keycode(key) for key in ('Control_L', 'Super_L', direction)]
        for code in keys:
            send(code, 1)
        for code in reversed(keys):
            send(code, 0)
        for code in held:
            send(code, 1)
        self.x.XFlush(self.display)

    def action(self, name):
        if name in ('overview-show', 'workspace-overview'):
            if self.overview() or (self.overview_child and self.overview_child.poll() is None):
                return
            with self.log_path.open('a') as log:
                self.overview_child = subprocess.Popen(
                    ['skippy-xd', '--paging-once'] if name == 'workspace-overview' else ['skippy-xd', '--desktop', '-1'],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            return
        self.hide()
        if name in ('window-previous', 'window-next'):
            self.cycle('Left' if name == 'window-previous' else 'Right')
        elif name in ('workspace-previous', 'workspace-next'):
            current, count = self.property('_NET_CURRENT_DESKTOP'), self.property('_NET_NUMBER_OF_DESKTOPS')
            if current and count and count[0] > 1:
                step = -1 if name == 'workspace-previous' else 1
                event = Event()
                event.message = Message(type=33, display=self.display, window=self.root,
                    message_type=self.atom('_NET_CURRENT_DESKTOP'), format=32)
                event.message.data[0] = (current[0] + step) % count[0]
                self.x.XSendEvent(self.display, self.root, 0, (1 << 19) | (1 << 20), C.byref(event))
                self.x.XFlush(self.display)


Open = C.CFUNCTYPE(I, C.c_char_p, I, V)
Close = C.CFUNCTYPE(None, I, V)


class Interface(C.Structure):
    _fields_ = [('open_restricted', Open), ('close_restricted', Close)]


class Touchpad:
    """A single libinput path context; the active seat user opens only this pad."""
    def __init__(self, path, settings, action):
        self.path, self.settings, self.action = path, settings, action
        self.lib = C.CDLL('libinput.so.10')
        signatures = {
            'libinput_path_create_context': (V, C.POINTER(Interface), V),
            'libinput_path_add_device': (V, V, C.c_char_p),
            'libinput_unref': (V, V), 'libinput_get_fd': (I, V),
            'libinput_dispatch': (I, V), 'libinput_get_event': (V, V),
            'libinput_event_get_type': (I, V), 'libinput_event_destroy': (None, V),
            'libinput_event_get_gesture_event': (V, V),
            'libinput_event_gesture_get_finger_count': (I, V),
            'libinput_event_gesture_get_dx_unaccelerated': (C.c_double, V),
            'libinput_event_gesture_get_dy_unaccelerated': (C.c_double, V),
        }
        for name, types in signatures.items():
            bind(self.lib, name, *types)

        def open_device(requested, flags, _userdata):
            if os.fsdecode(requested) != path:
                return -errno.EACCES
            try:
                return os.open(path, flags | os.O_CLOEXEC)
            except OSError as error:
                return -error.errno

        self.open_callback = Open(open_device)
        self.close_callback = Close(lambda fd, _: os.close(fd))
        self.interface = Interface(self.open_callback, self.close_callback)
        self.context = self.lib.libinput_path_create_context(C.byref(self.interface), None)
        if not self.context:
            raise RuntimeError('Cannot create libinput context.')
        if not self.lib.libinput_path_add_device(self.context, os.fsencode(path)):
            self.close()
            raise RuntimeError(f'Cannot open touchpad {path}.')
        self.fd = self.lib.libinput_get_fd(self.context)
        self.fingers, self.x, self.y, self.fired = 0, 0.0, 0.0, False

    def close(self):
        if self.context:
            self.lib.libinput_unref(self.context)
            self.context = None

    def dispatch(self):
        if self.lib.libinput_dispatch(self.context) != 0:
            raise OSError(errno.EIO, 'Touchpad read failed')
        while event := self.lib.libinput_get_event(self.context):
            try:
                kind = self.lib.libinput_event_get_type(event)
                if kind == 2:  # LIBINPUT_EVENT_DEVICE_REMOVED
                    raise OSError(errno.ENODEV, 'Touchpad disconnected')
                if kind not in (800, 801, 802):
                    continue
                gesture = self.lib.libinput_event_get_gesture_event(event)
                if kind == 800:  # SWIPE_BEGIN
                    self.fingers = self.lib.libinput_event_gesture_get_finger_count(gesture)
                    self.x, self.y, self.fired = 0.0, 0.0, False
                elif kind == 802:  # SWIPE_END, including cancellation
                    self.fingers = 0
                elif not self.fired and self.fingers in (3, 4):
                    # libinput-normalized gesture units; do not infer physical mm.
                    self.x += self.lib.libinput_event_gesture_get_dx_unaccelerated(gesture)
                    self.y += self.lib.libinput_event_gesture_get_dy_unaccelerated(gesture)
                    ax, ay = abs(self.x), abs(self.y)
                    threshold, ratio, bindings = self.settings
                    if max(ax, ay) < threshold or max(ax, ay) < min(ax, ay) * ratio:
                        continue
                    direction = ('left' if self.x < 0 else 'right') if ax > ay else ('up' if self.y < 0 else 'down')
                    name = bindings.get(f'{self.fingers}_{direction}')
                    if name:
                        self.fired = True
                        self.action(name)
            finally:
                self.lib.libinput_event_destroy(event)
