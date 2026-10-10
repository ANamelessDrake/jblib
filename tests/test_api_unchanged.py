"""Regression test: the pre-1.12 API produces byte-identical output.

The baseline is exported from git (default commit 569536d, the 1.11.0
release; override with JBLIB_BASELINE_REF) into a temporary directory
(under JBLIB_TEST_TMP when set). The test is skipped when git or the
baseline commit is not available.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(ROOT, 'tests', '_api_snapshot.py')
BASELINE_REF = os.environ.get('JBLIB_BASELINE_REF', '569536d')
NEW_NAMES = {'TransferProgress', 'supports_color', 'format_bytes', 'format_duration', 'transfer'}


def _snapshot(tree):
    env = dict(os.environ, COLUMNS='100', LINES='30', PYTHONDONTWRITEBYTECODE='1')
    env.pop('NO_COLOR', None)
    proc = subprocess.run([sys.executable, '-I', SNAPSHOT, tree], capture_output=True,
                          env=env, cwd=tree, check=True)
    return proc.stdout


class OldApiUnchanged(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if shutil.which('git') is None:
            raise unittest.SkipTest('git not available')
        check = subprocess.run(['git', '-C', ROOT, 'cat-file', '-e', BASELINE_REF + '^{commit}'],
                               capture_output=True)
        if check.returncode != 0:
            raise unittest.SkipTest(f'baseline {BASELINE_REF} not in this repository')
        cls.tmp = tempfile.mkdtemp(prefix='jblib-baseline-', dir=os.environ.get('JBLIB_TEST_TMP'))
        archive = subprocess.run(['git', '-C', ROOT, 'archive', BASELINE_REF, 'jblib'],
                                 capture_output=True, check=True).stdout
        subprocess.run(['tar', '-x', '-C', cls.tmp], input=archive, check=True)
        cls.old_raw = _snapshot(cls.tmp)
        cls.new_raw = _snapshot(ROOT)
        cls.old = json.loads(cls.old_raw)
        cls.new = json.loads(cls.new_raw)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, 'tmp', ''), ignore_errors=True)

    def test_every_old_output_is_byte_identical(self):
        keys = [k for k in self.old if k not in ('names', 'name_types')]
        self.assertGreater(len(keys), 100)
        for key in keys:
            with self.subTest(key=key):
                self.assertEqual(self.old[key], self.new[key])

    def test_old_names_still_exported_with_same_types(self):
        for name in self.old['names']:
            with self.subTest(name=name):
                self.assertIn(name, self.new['names'])
                self.assertEqual(self.old['name_types'][name], self.new['name_types'][name])

    def test_only_expected_names_added(self):
        added = set(self.new['names']) - set(self.old['names'])
        self.assertEqual(added, NEW_NAMES)

    def test_snapshot_contains_escape_sequences(self):
        # Guards against a snapshot that silently captured nothing.
        self.assertIn('\\u001b[', self.old_raw.decode())
        self.assertIn('\\u2588', self.old_raw.decode())


if __name__ == '__main__':
    unittest.main()
