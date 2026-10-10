"""
Transfer progress display for downloads, uploads, hashing and unpacking.

TransferProgress is a thread safe progress line that works as a boto3
transfer Callback (call it with the number of new bytes). On an interactive
terminal it redraws one line in place with a colored bar, the amount done,
a smoothed speed and an ETA. When the stream is not a terminal, or NO_COLOR
is set, it writes a plain line every 10% instead, with no escape codes.
"""

import os
import shutil
import sys
import threading
import time
from collections import deque

from ..color.colorize import _ESC, _RESET, _RGB, _interpolate

__all__ = ['TransferProgress', 'supports_color', 'format_bytes', 'format_duration']

_KB = 1024
_MB = 1024 ** 2
_GB = 1024 ** 3
_TB = 1024 ** 4


def supports_color(stream=None):
    """Return True when ANSI colors and in-place redraws are safe on stream.

    False when the stream is not a TTY, when the NO_COLOR environment
    variable is set to a non-empty value, or when TERM is "dumb".

    Args:
        stream: A file-like object. Defaults to sys.stdout at call time.
    """
    if stream is None:
        stream = sys.stdout
    if os.environ.get('NO_COLOR'):
        return False
    if os.environ.get('TERM') == 'dumb':
        return False
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError, OSError):
        return False


def format_bytes(n):
    """Format a byte count with binary units: "512 B", "1.5 KB", "575.1 MB"."""
    n = float(n)
    sign = '-' if n < 0 else ''
    n = abs(n)
    if n < _KB:
        return f'{sign}{int(n)} B'
    for size, unit in ((_TB, 'TB'), (_GB, 'GB'), (_MB, 'MB'), (_KB, 'KB')):
        if n >= size:
            return f'{sign}{n / size:.1f} {unit}'
    return f'{sign}{int(n)} B'  # pragma: no cover


def format_duration(seconds):
    """Format seconds as M:SS, or H:MM:SS from one hour up.

    Returns "--:--" for None, negative, infinite or NaN values.
    """
    if seconds is None:
        return '--:--'
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return '--:--'
    if seconds != seconds or seconds < 0 or seconds == float('inf'):
        return '--:--'
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f'{hours}:{minutes:02d}:{secs:02d}'
    return f'{minutes}:{secs:02d}'


def _scale_for(total):
    """Pick the divisor and unit used for the "done / total" figures."""
    if total < _KB:
        return 1, 'B'
    if total < _MB:
        return _KB, 'KB'
    if total < 10 * _GB:
        return _MB, 'MB'
    return _GB, 'GB'


class TransferProgress:
    """Thread safe progress line for byte transfers or item counts.

    Args:
        total: Expected final value (bytes, or items when unit="items").
        label: Text shown at the start of the line.
        color: Use a red to green gradient bar when the stream supports color.
        stream: Output stream. Defaults to sys.stderr at construction time.
        quiet: Print nothing at all.
        unit: "bytes" (default) or "items".

    Use it as a callable (boto3 Callback compatible), or call update(n),
    set(value) and finish(). It also works as a context manager, which
    calls finish() on a clean exit.

    Example:
        with TransferProgress(size, label="Download") as progress:
            s3.download_file(bucket, key, path, Callback=progress)
    """

    REDRAW_INTERVAL = 0.1     # seconds between in-place redraws (about 10 per second)
    SPEED_WINDOW = 5.0        # seconds of history used for the smoothed speed
    BAR_MIN = 10
    BAR_MAX = 40

    def __init__(self, total, label="Download", color=True, stream=None,
                 quiet=False, unit="bytes"):
        if unit not in ('bytes', 'items'):
            raise ValueError(f'Unknown unit: {unit} (use "bytes" or "items")')
        self.total = max(0, int(total or 0))
        self.label = label
        self.unit = unit
        self.quiet = quiet
        self.stream = stream if stream is not None else sys.stderr
        self.interactive = (not quiet) and supports_color(self.stream)
        self.color = bool(color) and self.interactive
        self.value = 0
        self.finished = False
        self._lock = threading.Lock()
        self._start = time.monotonic()
        self._samples = deque([(self._start, 0)])
        self._last_draw = 0.0
        self._drew_full = False
        self._last_decile = 0
        self._line_open = False

    # -- public API -------------------------------------------------------

    def __call__(self, n):
        self.update(n)

    def update(self, n):
        """Add n to the current value."""
        with self._lock:
            self._advance(self.value + n)

    def set(self, value):
        """Set the current value to an absolute amount."""
        with self._lock:
            self._advance(value)

    def finish(self):
        """Print the final line with the average speed and elapsed time."""
        with self._lock:
            if self.finished:
                return
            self.finished = True
            if self.quiet:
                return
            line = self._final_text()
            if self.interactive:
                self._write('\r' + self._pad(self._render(final=True)) + '\n')
            else:
                self._write(line + '\n')
            self._line_open = False

    @property
    def fraction(self):
        """Completed fraction, clamped to 0..1."""
        if self.total <= 0:
            return 1.0 if self.finished else 0.0
        return max(0.0, min(1.0, self.value / self.total))

    @property
    def percent(self):
        """Completed percentage as an integer, 100 only when complete."""
        frac = self.fraction
        pct = int(frac * 100)
        if frac < 1.0 and pct >= 100:
            pct = 99
        return pct

    @property
    def elapsed(self):
        return time.monotonic() - self._start

    def speed(self):
        """Smoothed rate in units per second over the last few seconds."""
        if len(self._samples) < 2:
            return 0.0
        t0, v0 = self._samples[0]
        t1, v1 = self._samples[-1]
        if t1 - t0 <= 0:
            return 0.0
        return max(0.0, (v1 - v0) / (t1 - t0))

    def eta(self):
        """Estimated seconds remaining, or None when unknown."""
        rate = self.speed()
        if self.total <= 0 or rate <= 0:
            return None
        return max(0.0, (self.total - self.value) / rate)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.finish()
        else:
            with self._lock:
                if self._line_open and not self.quiet:
                    self._write('\n')
                    self._line_open = False
        return False

    # -- internals (called with the lock held) ------------------------------

    def _advance(self, value):
        if self.finished:
            return
        self.value = value
        now = time.monotonic()
        self._samples.append((now, value))
        while len(self._samples) > 2 and now - self._samples[1][0] >= self.SPEED_WINDOW:
            self._samples.popleft()
        if self.quiet:
            return
        complete = self.total > 0 and value >= self.total
        if self.interactive:
            if complete:
                if not self._drew_full:
                    self._drew_full = True
                    self._draw(now)
            elif now - self._last_draw >= self.REDRAW_INTERVAL:
                self._draw(now)
        else:
            decile = 10 if complete else int(self.fraction * 10)
            if decile > self._last_decile:
                self._last_decile = decile
                self._write(self._plain_text() + '\n')

    def _draw(self, now):
        self._last_draw = now
        self._line_open = True
        self._write('\r' + self._pad(self._render()))

    def _write(self, text):
        try:
            self.stream.write(text)
            self.stream.flush()
        except (OSError, ValueError):
            pass

    def _width(self):
        return max(20, shutil.get_terminal_size(fallback=(80, 24)).columns - 1)

    def _pad(self, rendered):
        text, visible = rendered
        return text + ' ' * max(0, self._width() - visible)

    def _amounts(self):
        if self.unit == 'items':
            return f'{self.value} / {self.total} items'
        div, unit = _scale_for(self.total)
        if div == 1:
            return f'{self.value} / {self.total} {unit}'
        return f'{self.value / div:.1f} / {self.total / div:.1f} {unit}'

    def _rate(self, rate):
        if self.unit == 'items':
            return f'{rate:.0f} items/s'
        return f'{format_bytes(rate)}/s'

    def _tail(self, final=False):
        if final:
            elapsed = self.elapsed
            avg = self.value / elapsed if elapsed > 0 else 0.0
            return f'{self._amounts()}  avg {self._rate(avg)}  in {format_duration(elapsed)}'
        return f'{self._amounts()}  {self._rate(self.speed())}  ETA {format_duration(self.eta())}'

    def _plain_text(self):
        return f'{self.label} {self.percent:3d}%  {self._tail()}'

    def _final_text(self):
        pct = 100 if self.total <= 0 or self.value >= self.total else self.percent
        return f'{self.label} {pct:3d}%  {self._tail(final=True)}'

    def _render(self, final=False):
        """Return (text, visible_length) for the interactive line."""
        frac = 1.0 if final and (self.total <= 0 or self.value >= self.total) else self.fraction
        pct = int(frac * 100) if frac >= 1.0 else self.percent
        head = f'{self.label} '
        tail = f' {pct:3d}%  {self._tail(final=final)}'
        room = self._width() - len(head) - len(tail)
        bar_len = min(self.BAR_MAX, room)
        if bar_len < self.BAR_MIN:
            text = (head + tail.lstrip())[:self._width()]
            return text, len(text)
        filled = int(round(bar_len * frac))
        if self.color:
            start, end = _RGB['bright_red'], _RGB['bright_green']
            parts = []
            for i in range(filled):
                r, g, b = _interpolate(start, end, i / max(bar_len - 1, 1))
                parts.append(f'{_ESC}38;2;{r};{g};{b}m█')
            parts.append(f'{_ESC}90m' + '▬' * (bar_len - filled) + _RESET)
            bar = ''.join(parts)
        else:
            bar = '█' * filled + '▬' * (bar_len - filled)
        return head + bar + tail, len(head) + bar_len + len(tail)
