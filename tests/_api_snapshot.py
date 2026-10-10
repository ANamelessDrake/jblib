"""Capture the output of jblib's pre-1.12 public API as a JSON document.

Run as: python3 tests/_api_snapshot.py <path containing the jblib package>
The regression test runs this against the baseline commit and the working
tree and compares the two documents byte for byte.
"""
import contextlib
import io
import json
import sys

sys.path.insert(0, sys.argv[1])

import jblib  # noqa: E402

out = {}


def capture(key, func, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = func(*args, **kwargs)
    out[key] = {'stdout': buf.getvalue(), 'result': repr(result)}


for value in (-0.5, 0, 0.0, 0.25, 0.5, 0.999, 1, 1.0, 1.5, 'bad'):
    for length in (10, 50):
        capture(f'progress_bar|{value!r}|{length}', jblib.progress_bar, value, length)
        capture(f'progress_bar_text|{value!r}|{length}', jblib.progress_bar, value, length, text_field='Copy')
        capture(f'colored_progress_bar|{value!r}|{length}', jblib.colored_progress_bar, value, length)
        capture(f'colored_progress_bar_text|{value!r}|{length}', jblib.colored_progress_bar, value, length, text_field='Copy')

for i, kwargs in enumerate([
        {}, {'fg': 'red'}, {'fg': 'orange', 'bold': True}, {'fg': (1, 2, 3), 'bg': (4, 5, 6)},
        {'fg': 'Bright Blue', 'bg': 'yellow', 'underline': True, 'italic': True},
        {'bg': 'black', 'dim': True, 'reverse': True, 'strikethrough': True}]):
    capture(f'jbcolor|{i}', jblib.jbcolor, 'Hello', **kwargs)

for i, kwargs in enumerate([
        {}, {'title': 'Greeting', 'color': 'blue'},
        {'title': 'Info', 'color': 'teal', 'rounded': True, 'vpadding': 1},
        {'title': 'Status', 'color': (10, 200, 30), 'title_color': 'red', 'padding': 3},
        {'width': 40}, {'fullwidth': True}, {'fullwidth': True, 'margin': 4, 'color': 'green'}]):
    capture(f'border|{i}', jblib.border, 'Line 1\nLonger line 2\n' + jblib.jbcolor('PASS', fg='green'), **kwargs)

capture('gradient|1', jblib.gradient, 'Hello World', 'red', 'blue')
capture('gradient|2', jblib.gradient, 'Smooth', (255, 0, 0), (0, 0, 255), bold=True)
capture('gradient|3', jblib.gradient, '', 'red', 'blue')
capture('gradient|4', jblib.gradient, 'x', 'red', 'blue')
capture('rainbow|1', jblib.rainbow, 'Rainbow Text!')
capture('rainbow|2', jblib.rainbow, 'Bold', bold=True)
capture('fade|1', jblib.fade, 'Breathing effect', 'red', 'blue')
capture('fade|2', jblib.fade, 'ab', (1, 2, 3), 'orange', bold=True)
capture('cycle|1', jblib.cycle, 'Alternating!', ['red', 'blue', 'green'])
capture('cycle|2', jblib.cycle, 'Flag', [(255, 0, 0), (255, 255, 255), (0, 0, 255)], bold=True)
capture('cycle|3', jblib.cycle, 'none', [])
capture('pulse|1', jblib.pulse, 'ALERT', 'red', 'yellow', cycles=1, speed=0, steps=3)
capture('hilightV2', lambda: [getattr(jblib.hilightV2('x'), c)(bold=b)
                              for c in ('red', 'green', 'yellow', 'blue', 'purple', 'teal', 'white')
                              for b in (False, True)])
capture('hilight', lambda: [getattr(jblib.hilight('x'), c)(bold=b, highlight=h)
                            for c in ('red', 'green', 'yellow', 'blue', 'purple', 'teal', 'white')
                            for b in (False, True) for h in (False, True)])
capture('convert', lambda: [jblib.convert_time_from_seconds(3725), jblib.IP2Int('10.1.2.3'),
                            jblib.Int2IP(167838211), jblib.urlcode('a b/c'), jblib.urlcode('a%20b')])
out['Color'] = {k: v for k, v in vars(jblib.Color).items() if not k.startswith('_')}
out['BgColor'] = {k: v for k, v in vars(jblib.BgColor).items() if not k.startswith('_')}
out['names'] = sorted(n for n in dir(jblib) if not n.startswith('_'))
out['name_types'] = {n: type(getattr(jblib, n)).__name__ for n in out['names']}

sys.stdout.write(json.dumps(out, sort_keys=True, ensure_ascii=True))
