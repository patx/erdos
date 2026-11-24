# SPDX-License-Identifier: MIT
"""Wayland output settings and an independent confirmation process."""
import json
import math
import select
import sys

import settings

TRANSFORMS = ('normal', '90', '180', '270', 'flipped', 'flipped-90', 'flipped-180', 'flipped-270')


def mode_id(mode):
    return f"{mode['width']}x{mode['height']}@{mode['refresh']}Hz"


def outputs():
    result = []
    for item in json.loads(settings.run('wlr-randr', '--json')):
        modes = item.get('modes', [])
        current = next((mode for mode in modes if mode.get('current')), None)
        enabled = bool(item.get('enabled') and current)
        position = item.get('position') or {}
        result.append(dict(
            name=item['name'], primary=item['name'].startswith(('eDP-', 'LVDS-', 'DSI-')),
            modes=list(dict.fromkeys(mode_id(mode) for mode in modes)),
            mode=mode_id(current) if enabled else None, scale=float(item.get('scale') or 1),
            x=position.get('x', 0), y=position.get('y', 0),
            transform=item.get('transform', 'normal'),
            preferred=next((mode_id(mode) for mode in modes if mode.get('preferred')), None),
        ))
    return result


def topology(items):
    return sorted(item['name'] for item in items)


def valid_scale(scale):
    return type(scale) in (int, float) and math.isfinite(scale) and scale > 0


def resolution(mode):
    return mode.split('@', 1)[0]


def current_settings(item):
    return {key: item[key] for key in ('mode', 'scale', 'x', 'y', 'transform')}


def output_args(item, target):
    mode, scale, transform = target['mode'], target['scale'], target['transform']
    if mode not in item['modes']:
        raise ValueError(f'{item["name"]} no longer advertises {mode}. Refresh displays.')
    if not valid_scale(scale):
        raise ValueError(f'Invalid scale for {item["name"]}.')
    if transform not in TRANSFORMS or any(type(target[axis]) is not int for axis in ('x', 'y')):
        raise ValueError(f'Invalid rotation or position for {item["name"]}.')
    args = ['--output', item['name']]
    if item['mode'] is None:
        args += ['--on']
    if mode != item['mode']:
        args += ['--mode', mode]
    return args + ['--scale', str(scale), '--transform', transform, '--pos', f'{target["x"]},{target["y"]}']


def layout(items, selections):
    active = [item for item in items if item['mode']]
    if not active or set(selections) != {item['name'] for item in active}:
        raise ValueError('Connected displays changed. Refresh the display list.')
    command = ['wlr-randr']
    for item in active:
        command.extend(output_args(item, selections[item['name']]))
    return command


def automatic():
    prefs = settings.preferences()
    items = outputs()
    saved = prefs.get('display_modes', {})
    if topology(items) != saved.get('outputs'):
        saved = {}
    configurations = saved.get('configurations', {})
    command = ['wlr-randr']
    if configurations:
        try:
            available = {item['name']: item for item in items}
            for name, target in configurations.items():
                command.extend(output_args(available[name], target))
        except (KeyError, TypeError, ValueError):
            command = ['wlr-randr']
        if len(command) > 1:
            settings.run(*command)
            return
    if not prefs['automatic_displays']:
        # Older saves have no arrangement. Keep the current position and rotation.
        for item in items:
            legacy = saved.get('modes', {}).get(item['name'])
            scale = saved.get('scales', {}).get(item['name'])
            if item['mode'] and (legacy or valid_scale(scale)):
                mode = next((mode for mode in item['modes']
                             if mode == legacy or resolution(mode) == legacy), item['mode'])
                command.extend(output_args(item, {**current_settings(item), 'mode': mode,
                                                  'scale': scale if valid_scale(scale) else item['scale']}))
        if len(command) > 1:
            settings.run(*command)
        return

    edge = 0
    for item in sorted(items, key=lambda item: (not item['primary'], item['name'])):
        legacy = saved.get('modes', {}).get(item['name'])
        modes = item['modes']
        mode = next((mode for mode in modes if mode == legacy or resolution(mode) == legacy), None)
        mode = mode or item['preferred'] or item['mode'] or next(iter(modes), None)
        if not mode:
            continue
        scale = saved.get('scales', {}).get(item['name'])
        if not valid_scale(scale):
            scale = item['scale']
        transform = item['transform']
        command.extend(output_args(item, dict(mode=mode, scale=scale, x=edge, y=0, transform=transform)))
        width, height = map(int, resolution(mode).split('x'))
        edge += round((height if transform in ('90', '270', 'flipped-90', 'flipped-270') else width) / scale)
    if len(command) > 1:
        settings.run(*command)


def restore(items):
    now = outputs()
    if topology(now) != topology(items):
        automatic()
        return
    command = ['wlr-randr']
    available = {item['name']: item for item in now}
    for item in items:
        if item['mode']:
            command.extend(output_args(available[item['name']], current_settings(item)))
        else:
            command.extend(['--output', item['name'], '--off'])
    settings.run(*command)


def trial():
    previous = None
    confirmed = False
    try:
        selection = json.loads(sys.stdin.readline())
        before = outputs()
        command = layout(before, selection)
        previous = before
        settings.run(*command)
        print(json.dumps({'status': 'ready', 'seconds': 15}), flush=True)
        ready, _, _ = select.select([sys.stdin], [], [], 15)
        answer = sys.stdin.readline().strip() if ready else ''
        if answer == 'keep':
            current = outputs()
            active = {item['name']: current_settings(item) for item in current if item['mode']}
            if (topology(current) != topology(previous) or active.keys() != selection.keys()
                    or any(any(item[key] != selection[name][key] for key in ('mode', 'x', 'y', 'transform'))
                           or not math.isclose(item['scale'], selection[name]['scale'], abs_tol=0.005)
                           for name, item in active.items())):
                raise ValueError('Display settings did not match the requested changes.')
            settings.save_preferences(display_modes={'outputs': topology(previous), 'configurations': active})
            confirmed = True
            print(json.dumps({'status': 'kept'}), flush=True)
        else:
            restore(previous)
            previous = None
            print(json.dumps({'status': 'restored'}), flush=True)
    except Exception as error:
        message = str(error)
        if previous is not None and not confirmed:
            try:
                restore(previous)
            except Exception as failure:
                message += f' Could not restore displays: {failure}'
        try:
            print(json.dumps({'status': 'error', 'message': message}), flush=True)
        except BrokenPipeError:
            pass


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    trial()
