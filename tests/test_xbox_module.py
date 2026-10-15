import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SHELL = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('sh')


class XboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sys = self.root / 'input'
        self.sys.mkdir()
        self.log = self.root / 'events'
        self.device()

    def tearDown(self):
        self.temp.cleanup()

    def device(self, event='event10', bus='0005', vendor='045e', product='0b22', name='Xbox Wireless Controller'):
        p = self.sys / event / 'device'
        (p / 'id').mkdir(parents=True, exist_ok=True)
        for key, val in dict(bustype=bus, vendor=vendor, product=product).items():
            (p / 'id' / key).write_text(val + '\n')
        (p / 'name').write_text(name + '\n')

    def run_script(self, command='release_unknown "$SYS/event10"', held='00f0*', race=False, fail=False):
        env = dict(os.environ, SYS=self.sys.as_posix(), LIB=(ROOT / 'modules/xbox-unknown-key/lib.sh').as_posix(),
                   EVENTS=self.log.as_posix(), MODDIR=self.root.as_posix(), HELD=held,
                   RACE='1' if race else '0', FAIL='1' if fail else '0')
        setup = ''
        if os.name == 'nt':
            setup = 'SYS=$(cygpath -u "$SYS"); LIB=$(cygpath -u "$LIB"); EVENTS=$(cygpath -u "$EVENTS"); MODDIR=$(cygpath -u "$MODDIR"); '
        mock = '''
getevent() {
    [ "$RACE" = 0 ] || echo 1234 > "$SYS/event10/device/id/vendor"
    printf '  00ef  %s 0130\n' "$HELD"
}
sendevent() {
    [ "$FAIL" = 0 ] || return 1
    printf '%s\n' "$*" >> "$EVENTS"
}
seen='|'
'''
        return subprocess.run([SHELL, '-c', setup + '. "$LIB"; ' + mock + command], env=env,
                              text=True, capture_output=True, timeout=15)

    def test_exact_release_and_sync_only(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.log.read_text().splitlines(), ['/dev/input/event10 1 240 0', '/dev/input/event10 0 0 0'])

    def test_other_xbox_product_supported(self):
        self.device(product='02fd', name='Xbox Elite Wireless Controller')
        self.assertEqual(self.run_script().returncode, 0)

    def test_non_bluetooth_refused(self):
        self.device(bus='0003')
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertFalse(self.log.exists())

    def test_non_microsoft_refused(self):
        self.device(vendor='1234')
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertFalse(self.log.exists())

    def test_non_xbox_microsoft_refused(self):
        self.device(name='Microsoft Keyboard')
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertFalse(self.log.exists())

    def test_unheld_or_different_key_refused(self):
        for token in ['00f0', '0130*', '100f0*', '00f0*x']:
            self.assertNotEqual(self.run_script(held=token).returncode, 0)
            self.assertFalse(self.log.exists())

    def test_node_reuse_race_refused(self):
        self.assertNotEqual(self.run_script(race=True).returncode, 0)
        self.assertFalse(self.log.exists())

    def test_once_per_connection_and_multiple_controllers(self):
        self.device(event='event11', product='02fd')
        self.assertEqual(self.run_script('scan_once "$SYS"; scan_once "$SYS"').returncode, 0)
        self.assertEqual(len(self.log.read_text().splitlines()), 4)

    def test_disconnect_reconnect_rearms(self):
        r = self.run_script('scan_once "$SYS"; mv "$SYS/event10" "$MODDIR/saved"; scan_once "$SYS"; mv "$MODDIR/saved" "$SYS/event10"; scan_once "$SYS"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.log.read_text().splitlines()), 4)

    def test_failed_release_not_marked_handled(self):
        r = self.run_script('scan_once "$SYS"; test "$seen" = "|"', fail=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.log.exists())

    def test_shell_syntax(self):
        for script in (ROOT / 'modules/xbox-unknown-key').glob('*.sh'):
            r = subprocess.run([SHELL, '-n', script.as_posix()], text=True, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_package_reproducible_disabled_no_mount(self):
        from tools.build_xbox import build
        p = build()
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        build()
        self.assertEqual(digest, hashlib.sha256(p.read_bytes()).hexdigest())
        with ZipFile(p) as z:
            self.assertEqual(z.read('disable'), b'')
            self.assertEqual(z.read('skip_mount'), b'')
            self.assertFalse(any(n.startswith('system/') for n in z.namelist()))
            for line in z.read('SHA256SUMS').decode().splitlines():
                checksum, name = line.split('  ')
                self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(), checksum)
