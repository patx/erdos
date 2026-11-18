# SPDX-License-Identifier: MIT
"""Advertised RandR modes and a short-lived, crash-safe confirmation process."""
import json
import re
import select
import sys
import settings


def outputs():
    result = []
    current = None
    for line in settings.run('xrandr', '--query').splitlines():
        header = re.match(r'^(\S+) (connected|disconnected)\b(.*)', line)
        if header:
            current = None
            if header[2] != 'connected':
                continue
            geometry = re.search(r'(\d+)x(\d+)\+(\d+)\+(\d+)', header[3])
            current = dict(name=header[1], primary=' primary ' in line, modes=[], mode=None,
                           rate=None, x=0, y=0, width=0, height=0)
            if geometry:
                current.update(zip(('width','height','x','y'), map(int, geometry.groups())))
                # ErdOS configures normal orientation; do not disturb custom rotations.
                rotation = header[3][geometry.end():].split('(')[0].strip()
                current['rotated'] = bool(re.search(r'\b(left|right|inverted)\b|[xy] axis', rotation))
            result.append(current)
        elif current is not None:
            mode = re.match(r'^\s+(\d+x\d+\S*)\s+(.+)', line)
            if mode:
                rates = re.findall(r'(\d+(?:\.\d+)?)([+*]*)', mode[2])
                if not rates:
                    continue
                current['modes'].append(mode[1])
                for rate, flags in rates:
                    if '*' in flags:
                        current.update(mode=mode[1], rate=rate)
    return result


def topology(items):
    return sorted(item['name'] for item in items)


def layout(items, selections):
    active = [item for item in items if item['mode']]
    if not active:
        raise ValueError('No active display detected.')
    if set(selections) != {item['name'] for item in active}:
        raise ValueError('Connected displays changed. Refresh the display list.')
    if any(item.get('rotated') for item in active):
        raise ValueError('Return rotated displays to normal orientation before using this editor.')
    ordered = sorted(active, key=lambda item:item['x'])
    edge = 0
    row = True
    for item in ordered:
        row = row and item['x'] == edge and item['y'] == 0
        edge += item['width']
    command = ['xrandr']
    edge = 0
    for item in ordered:
        mode = selections[item['name']]
        if mode not in item['modes']:
            raise ValueError(f'{item["name"]} no longer advertises {mode}. Refresh the display list.')
        command += ['--output', item['name'], '--mode', mode,
                    '--pos', f'{edge if row else item["x"]}x{item["y"]}']
        if item['primary']:
            command.append('--primary')
        edge += int(re.match(r'\d+',mode)[0])
    return command


def restore(items):
    now = outputs()
    if topology(now) != topology(items):
        settings.run('erdos-displays','--apply')
        return
    command = ['xrandr']
    for item in items:
        command += ['--output',item['name']]
        if item['mode']:
            command += ['--mode',item['mode'], '--pos',f'{item["x"]}x{item["y"]}']
            if item['rate']:
                command += ['--rate',item['rate']]
            if item['primary']:
                command += ['--primary']
        else:
            command += ['--off']
    settings.run(*command)


def restore_saved():
    saved = settings.preferences().get('display_modes')
    if not saved:
        return
    current = outputs()
    if topology(current) == saved['outputs']:
        try:
            command = layout(current, saved['modes'])
        except ValueError:
            return  # A replaced monitor may advertise a different set of modes.
        settings.run(*command)


def trial():
    """Pipe protocol: JSON selection, then keep/revert. EOF also restores."""
    previous = None
    confirmed = False
    try:
        selection = json.loads(sys.stdin.readline())
        previous = outputs()
        command = layout(previous, selection)
        settings.run(*command)
        print(json.dumps({'status':'ready', 'seconds':15}), flush=True)
        ready, _, _ = select.select([sys.stdin], [], [], 15)
        answer = sys.stdin.readline().strip() if ready else ''
        if answer == 'keep':
            current = outputs()
            if topology(current) != topology(previous) or any(
                    item['mode'] != selection.get(item['name']) for item in current if item['mode']):
                raise ValueError('Displays changed during confirmation. The selection was not saved.')
            settings.save_preferences(display_modes={'outputs':topology(previous), 'modes':selection})
            confirmed = True
            print(json.dumps({'status':'kept'}), flush=True)
        else:
            restore(previous)
            previous = None
            print(json.dumps({'status':'restored'}), flush=True)
    except Exception as error:
        message = str(error)
        if previous is not None and not confirmed:
            try:
                restore(previous)
            except Exception as failure:
                message += f' Could not restore displays: {failure}'
        try:
            print(json.dumps({'status':'error', 'message':message}), flush=True)
        except BrokenPipeError:
            pass


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    trial()
