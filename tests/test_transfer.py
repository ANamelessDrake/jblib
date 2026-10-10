"""Tests for jblib.progress_bar.transfer."""
import io
import os
import re
import threading
import unittest
from unittest import mock

from jblib import TransferProgress, format_bytes, format_duration, supports_color
from jblib.progress_bar import transfer

ESC = '\x1b'
MB = 1024 * 1024


class FakeTTY(io.StringIO):
    def isatty(self):
        return True


class Clock:
    """Controllable replacement for time.monotonic inside transfer.py."""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now


def tty_env():
    env = {k: v for k, v in os.environ.items() if k != 'NO_COLOR'}
    env['TERM'] = 'xterm-256color'
    env['COLUMNS'] = '120'
    return mock.patch.dict(os.environ, env, clear=True)


class FormatTests(unittest.TestCase):

    def test_format_bytes(self):
        self.assertEqual(format_bytes(0), '0 B')
        self.assertEqual(format_bytes(1023), '1023 B')
        self.assertEqual(format_bytes(1024), '1.0 KB')
        self.assertEqual(format_bytes(1536), '1.5 KB')
        self.assertEqual(format_bytes(int(575.1 * MB)), '575.1 MB')
        self.assertEqual(format_bytes(3 * 1024 ** 3), '3.0 GB')
        self.assertEqual(format_bytes(2 * 1024 ** 4), '2.0 TB')

    def test_format_duration(self):
        self.assertEqual(format_duration(0), '0:00')
        self.assertEqual(format_duration(5), '0:05')
        self.assertEqual(format_duration(65), '1:05')
        self.assertEqual(format_duration(3599), '59:59')
        self.assertEqual(format_duration(3600), '1:00:00')
        self.assertEqual(format_duration(3725), '1:02:05')
        for bad in (None, -1, float('inf'), float('nan'), 'x'):
            self.assertEqual(format_duration(bad), '--:--')


class SupportsColorTests(unittest.TestCase):

    def test_tty_with_clean_env(self):
        with tty_env():
            self.assertTrue(supports_color(FakeTTY()))

    def test_not_a_tty(self):
        with tty_env():
            self.assertFalse(supports_color(io.StringIO()))

    def test_no_color(self):
        with tty_env(), mock.patch.dict(os.environ, {'NO_COLOR': '1'}):
            self.assertFalse(supports_color(FakeTTY()))

    def test_empty_no_color_is_ignored(self):
        with tty_env(), mock.patch.dict(os.environ, {'NO_COLOR': ''}):
            self.assertTrue(supports_color(FakeTTY()))

    def test_dumb_terminal(self):
        with tty_env(), mock.patch.dict(os.environ, {'TERM': 'dumb'}):
            self.assertFalse(supports_color(FakeTTY()))

    def test_stream_without_isatty(self):
        self.assertFalse(supports_color(object()))


class MathTests(unittest.TestCase):

    def setUp(self):
        self.clock = Clock()
        patcher = mock.patch.object(transfer.time, 'monotonic', self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_speed_eta_and_percent(self):
        p = TransferProgress(100 * MB, stream=io.StringIO(), quiet=True)
        for _ in range(4):
            self.clock.now += 1
            p(10 * MB)
        self.assertEqual(p.value, 40 * MB)
        self.assertEqual(p.percent, 40)
        self.assertAlmostEqual(p.speed(), 10 * MB)
        self.assertAlmostEqual(p.eta(), 6.0)

    def test_speed_is_smoothed_over_recent_window(self):
        p = TransferProgress(1000 * MB, stream=io.StringIO(), quiet=True)
        for _ in range(10):          # slow phase: 1 MB/s for 10 s
            self.clock.now += 1
            p(1 * MB)
        for _ in range(10):          # fast phase: 20 MB/s for 10 s
            self.clock.now += 1
            p(20 * MB)
        # Only the last few seconds count, so the old slow phase is gone.
        self.assertAlmostEqual(p.speed(), 20 * MB)

    def test_percent_never_shows_100_before_complete(self):
        p = TransferProgress(1000, stream=io.StringIO(), quiet=True)
        p.set(999)
        self.assertEqual(p.percent, 99)
        p.set(1000)
        self.assertEqual(p.percent, 100)
        p.set(5000)
        self.assertEqual(p.fraction, 1.0)

    def test_eta_unknown_without_progress(self):
        p = TransferProgress(1000, stream=io.StringIO(), quiet=True)
        self.assertIsNone(p.eta())

    def test_bad_unit(self):
        with self.assertRaises(ValueError):
            TransferProgress(10, unit='parsecs')


class NonTTYOutputTests(unittest.TestCase):

    def test_plain_lines_every_ten_percent_without_escapes(self):
        with tty_env():
            out = io.StringIO()
            p = TransferProgress(1000 * MB, label='Download', stream=out)
            for _ in range(100):
                p(1000 * MB // 100)
            p.finish()
        text = out.getvalue()
        self.assertNotIn(ESC, text)
        self.assertNotIn('\r', text)
        lines = text.splitlines()
        # 10 decile lines (10% .. 100%) plus the final summary line.
        self.assertEqual(len(lines), 11)
        self.assertTrue(lines[0].startswith('Download  10%  100.0 / 1000.0 MB'))
        self.assertTrue(lines[9].startswith('Download 100%  1000.0 / 1000.0 MB'))
        self.assertRegex(lines[-1], r'^Download 100%  1000\.0 / 1000\.0 MB  avg .+/s  in \d+:\d\d$')

    def test_no_color_env_on_a_tty_is_plain(self):
        with tty_env(), mock.patch.dict(os.environ, {'NO_COLOR': '1'}):
            out = FakeTTY()
            with TransferProgress(1000, stream=out) as p:
                for _ in range(1000):
                    p(1)
        self.assertNotIn(ESC, out.getvalue())
        self.assertNotIn('\r', out.getvalue())
        self.assertEqual(len(out.getvalue().splitlines()), 11)

    def test_quiet_prints_nothing(self):
        for stream in (io.StringIO(), FakeTTY()):
            with tty_env():
                p = TransferProgress(1000, stream=stream, quiet=True)
                for _ in range(1000):
                    p(1)
                p.finish()
            self.assertEqual(stream.getvalue(), '')
            self.assertEqual(p.value, 1000)

    def test_items_unit(self):
        out = io.StringIO()
        p = TransferProgress(50, label='Unpack', stream=out, unit='items')
        for _ in range(50):
            p(1)
        p.finish()
        lines = out.getvalue().splitlines()
        self.assertTrue(lines[0].startswith('Unpack  10%  5 / 50 items  '))
        self.assertIn('items/s', lines[0])
        self.assertNotIn('MB', out.getvalue())
        self.assertRegex(lines[-1], r'^Unpack 100%  50 / 50 items  avg \d+ items/s  in ')

    def test_small_totals_use_small_units(self):
        out = io.StringIO()
        p = TransferProgress(512, stream=out)
        p(512)
        self.assertIn('512 / 512 B', out.getvalue())


class TTYOutputTests(unittest.TestCase):

    def setUp(self):
        self.clock = Clock()
        patcher = mock.patch.object(transfer.time, 'monotonic', self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_redraws_in_place_with_color_and_throttle(self):
        with tty_env():
            out = FakeTTY()
            p = TransferProgress(1000 * MB, stream=out)
            for _ in range(50):          # 50 updates within 50 ms: one redraw
                self.clock.now += 0.001
                p(1 * MB)
            self.assertEqual(out.getvalue().count('\r'), 1)
            self.clock.now += 0.2
            p(1 * MB)
            self.assertEqual(out.getvalue().count('\r'), 2)
            p.set(1000 * MB)             # 100% always drawn, even inside the throttle
            self.assertEqual(out.getvalue().count('\r'), 3)
            self.assertIn('100%', out.getvalue().split('\r')[-1])
            p.finish()
        text = out.getvalue()
        self.assertIn(ESC + '[38;2;', text)
        self.assertIn('█', text)
        self.assertTrue(text.endswith('\n'))
        self.assertIn('avg ', text.split('\r')[-1])

    def test_line_fits_terminal_width(self):
        with tty_env(), mock.patch.dict(os.environ, {'COLUMNS': '70'}):
            out = FakeTTY()
            p = TransferProgress(1368 * MB, label='Download', stream=out, color=False)
            p(575 * MB)
        line = out.getvalue().split('\r')[-1]
        self.assertNotIn(ESC, line)
        self.assertEqual(len(line), 69)
        self.assertIn('█', line)
        self.assertIn('▬', line)
        self.assertIn('575.0 / 1368.0 MB', line)

    def test_narrow_terminal_drops_bar(self):
        with tty_env(), mock.patch.dict(os.environ, {'COLUMNS': '40'}):
            out = FakeTTY()
            p = TransferProgress(1368 * MB, stream=out)
            p(575 * MB)
        line = out.getvalue().split('\r')[-1]
        self.assertNotIn('█', re.sub(r'\x1b\[[0-9;]*m', '', line))
        self.assertLessEqual(len(line), 39)


class ColorStopTests(unittest.TestCase):

    def bar_colors(self, **kwargs):
        with tty_env(), mock.patch.dict(os.environ, {'COLUMNS': '120'}):
            out = FakeTTY()
            p = TransferProgress(100, stream=out, **kwargs)
            p.set(100)
        codes = re.findall(r'\x1b\[38;2;(\d+);(\d+);(\d+)m\u2588', out.getvalue())
        self.assertEqual(len(codes), TransferProgress.BAR_MAX)
        return [tuple(map(int, c)) for c in codes]

    def test_default_is_red_to_green(self):
        codes = self.bar_colors()
        self.assertEqual(codes[0], (205, 0, 0))
        self.assertEqual(codes[-1], (0, 205, 0))

    def test_names(self):
        codes = self.bar_colors(colors=('blue', 'Bright White'))
        self.assertEqual(codes[0], (0, 0, 205))
        self.assertEqual(codes[-1], (255, 255, 255))

    def test_tuples(self):
        codes = self.bar_colors(colors=((10, 20, 30), (110, 120, 130)))
        self.assertEqual(codes[0], (10, 20, 30))
        self.assertEqual(codes[-1], (110, 120, 130))

    def test_three_stops(self):
        p = TransferProgress(1, stream=io.StringIO(), colors=('red', 'yellow', 'green'))
        self.assertEqual(p._gradient_at(0.0), (205, 0, 0))
        self.assertEqual(p._gradient_at(0.5), (205, 205, 0))
        self.assertEqual(p._gradient_at(1.0), (0, 205, 0))
        self.assertEqual(p._gradient_at(0.25), (205, 102, 0))
        codes = self.bar_colors(colors=('red', 'yellow', 'green'))
        self.assertEqual(codes[0], (205, 0, 0))
        # Mid-bar sits near yellow: red and green channels both high.
        r, g, b = codes[len(codes) // 2]
        self.assertGreater(min(r, g), 190)
        self.assertEqual(codes[-1], (0, 205, 0))

    def test_unknown_name_raises(self):
        with self.assertRaises(ValueError):
            TransferProgress(10, colors=('red', 'chartreuse'))
        with self.assertRaises(ValueError):
            TransferProgress(10, colors='red')
        with self.assertRaises(ValueError):
            TransferProgress(10, colors=())

    def test_colors_unused_without_tty(self):
        out = io.StringIO()
        p = TransferProgress(10, stream=out, colors=('blue', 'purple'))
        p(10)
        p.finish()
        self.assertNotIn(ESC, out.getvalue())


class ThreadSafetyTests(unittest.TestCase):

    def run_threads(self, stream):
        threads_n, per_thread, chunk = 16, 5000, 7
        total = threads_n * per_thread * chunk
        p = TransferProgress(total, stream=stream)
        barrier = threading.Barrier(threads_n)

        def worker():
            barrier.wait()
            for _ in range(per_thread):
                p(chunk)

        threads = [threading.Thread(target=worker) for _ in range(threads_n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        p.finish()
        return p, total

    def test_sixteen_threads_reach_exact_total_plain(self):
        out = io.StringIO()
        p, total = self.run_threads(out)
        self.assertEqual(p.value, total)
        self.assertEqual(p.percent, 100)
        lines = out.getvalue().splitlines()
        self.assertEqual(len(lines), 11)
        self.assertEqual([int(l.split()[1].rstrip('%')) for l in lines[:10]],
                         [10, 20, 30, 40, 50, 60, 70, 80, 90, 100])

    def test_sixteen_threads_reach_exact_total_tty(self):
        with tty_env():
            out = FakeTTY()
            p, total = self.run_threads(out)
        self.assertEqual(p.value, total)
        self.assertEqual(out.getvalue().count('100%'), 2)   # the 100% draw and the final line


class ContextManagerTests(unittest.TestCase):

    def test_finish_on_exit(self):
        out = io.StringIO()
        with TransferProgress(10, stream=out, unit='items') as p:
            p.update(10)
        self.assertTrue(p.finished)
        self.assertIn('avg', out.getvalue().splitlines()[-1])

    def test_finish_is_idempotent(self):
        out = io.StringIO()
        p = TransferProgress(10, stream=out)
        p(10)
        p.finish()
        p.finish()
        self.assertEqual(out.getvalue().count('avg'), 1)

    def test_exception_does_not_claim_completion(self):
        with tty_env():
            out = FakeTTY()
            with self.assertRaises(RuntimeError):
                with TransferProgress(100, stream=out) as p:
                    p(40)
                    raise RuntimeError('boom')
        self.assertFalse(p.finished)
        self.assertNotIn('avg', out.getvalue())
        self.assertTrue(out.getvalue().endswith('\n'))

    def test_updates_after_finish_are_ignored(self):
        out = io.StringIO()
        p = TransferProgress(10, stream=out)
        p(10)
        p.finish()
        before = out.getvalue()
        p(5)
        self.assertEqual(out.getvalue(), before)
        self.assertEqual(p.value, 10)


if __name__ == '__main__':
    unittest.main()
