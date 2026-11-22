# SPDX-License-Identifier: MIT
"""Wayland output modes and a short-lived, crash-safe confirmation process."""
import json
import select
import sys
import settings


def outputs():
    result = []
    for item in json.loads(settings.run('wlr-randr', '--json')):
        modes = item.get('modes', [])
        current = next((mode for mode in modes if mode.get('current')), None)
        enabled = bool(item.get('enabled') and current)
        scale = item.get('scale', 1) or 1
        position = item.get('position') or {}
        result.append(dict(name=item['name'], primary=item['name'].startswith(('eDP-', 'LVDS-', 'DSI-')),
            modes=list(dict.fromkeys(f"{mode['width']}x{mode['height']}" for mode in modes)),
            mode=f"{current['width']}x{current['height']}" if enabled else None,
            rate=str(current.get('refresh', 0)) if enabled else None,
            x=position.get('x',0), y=position.get('y',0), scale=scale,
            width=round(current['width']/scale) if enabled else 0,
            height=round(current['height']/scale) if enabled else 0,
            rotated=item.get('transform','normal') != 'normal',
            preferred=next((f"{mode['width']}x{mode['height']}" for mode in modes if mode.get('preferred')), None)))
    return result


def topology(items):
    return sorted(item['name'] for item in items)


def layout(items, selections):
    active = [item for item in items if item['mode']]
    if not active or set(selections) != {item['name'] for item in active}:
        raise ValueError('Connected displays changed. Refresh the display list.')
    if any(item.get('rotated') for item in active):
        raise ValueError('Return rotated displays to normal orientation before using this editor.')
    ordered = sorted(active, key=lambda item:item['x'])
    command = ['wlr-randr']
    edge = 0
    row = all(item['y'] == 0 for item in ordered)
    for item in ordered:
        mode = selections[item['name']]
        if mode not in item['modes']:
            raise ValueError(f'{item["name"]} no longer advertises {mode}. Refresh displays.')
        command += ['--output',item['name'],'--mode',mode,'--pos',f'{edge if row else item["x"]},{item["y"]}']
        edge += round(int(mode.split('x')[0])/item.get('scale',1))
    return command


def automatic():
    prefs = settings.preferences()
    if not prefs['automatic_displays']:
        return
    items = outputs()
    saved = prefs.get('display_modes', {})
    saved_modes = saved.get('modes', {}) if topology(items) == saved.get('outputs') else {}
    command = ['wlr-randr']
    edge = 0
    for item in sorted(items,key=lambda item:(not item['primary'],item['name'])):
        mode = saved_modes.get(item['name']) or item['preferred'] or item['mode'] or next(iter(item['modes']),None)
        if mode not in item['modes']:
            mode = item['preferred'] or next(iter(item['modes']),None)
        if not mode:
            continue
        command += ['--output',item['name'],'--on','--mode',mode,'--pos',f'{edge},0']
        edge += round(int(mode.split('x')[0])/item.get('scale',1))
    if len(command)>1:
        settings.run(*command)


def restore(items):
    now = outputs()
    if topology(now) != topology(items):
        automatic()
        return
    command = ['wlr-randr']
    for item in items:
        command += ['--output',item['name']]
        if item['mode']:
            mode=item['mode'] + ('@'+item['rate']+'Hz' if item['rate'] else '')
            command += ['--on','--mode',mode,'--pos',f'{item["x"]},{item["y"]}','--scale',str(item['scale'])]
        else:
            command += ['--off']
    settings.run(*command)


def trial():
    previous=None; confirmed=False
    try:
        selection=json.loads(sys.stdin.readline())
        previous=outputs()
        settings.run(*layout(previous,selection))
        print(json.dumps({'status':'ready','seconds':15}),flush=True)
        ready,_,_=select.select([sys.stdin],[],[],15)
        answer=sys.stdin.readline().strip() if ready else ''
        if answer=='keep':
            current=outputs()
            if topology(current)!=topology(previous) or any(item['mode']!=selection.get(item['name']) for item in current if item['mode']):
                raise ValueError('Displays changed during confirmation. Selection was not saved.')
            settings.save_preferences(display_modes={'outputs':topology(previous),'modes':selection})
            confirmed=True
            print(json.dumps({'status':'kept'}),flush=True)
        else:
            restore(previous);previous=None
            print(json.dumps({'status':'restored'}),flush=True)
    except Exception as error:
        message=str(error)
        if previous is not None and not confirmed:
            try:restore(previous)
            except Exception as failure:message+=f' Could not restore displays: {failure}'
        try:print(json.dumps({'status':'error','message':message}),flush=True)
        except BrokenPipeError:pass


if __name__=='__main__':
    sys.dont_write_bytecode=True
    trial()
