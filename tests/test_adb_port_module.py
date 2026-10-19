import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'modules/adb-port-publisher'
SHELL = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('sh')


class Harness(unittest.TestCase):
    """Runs the module scripts with mock getprop/ss/curl on PATH."""

    # MSYS would otherwise prefer its own real commands, and the mock files are
    # Windows paths; convert everything to POSIX form inside the shell.
    PROLOGUE = (
        'export PATH="$(cygpath -u "$MOCK_BIN"):$PATH"; '
        'for v in ADB_PORT_CONF ADB_PORT_STATE ADB_PORT_LOG ADB_PORT_LOCK ADB_PORT_PIDFILE '
        'PROP_TLS PROP_TCP PROP_PERSIST SS_PORT CURL_CALLS CURL_FAIL; do '
        'eval "export $v=\\$(cygpath -u \\"\\$$v\\")"; done; '
    )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.conf = self.root / 'conf'
        self.state = self.root / 'state'
        self.log = self.root / 'log'
        self.lock = self.root / 'lock'
        self.curl_calls = self.root / 'curl-calls'
        self.curl_fail = self.root / 'curl-fail'
        self.curl_fail.write_text('0')
        self.prop_tls = self.root / 'prop-tls'
        self.prop_tls.write_text('')
        self.prop_tcp = self.root / 'prop-tcp'
        self.prop_tcp.write_text('')
        self.prop_persist = self.root / 'prop-persist'
        self.prop_persist.write_text('')
        self.ss_port = self.root / 'ss-port'
        self.ss_port.write_text('')
        self.script = self.root / 'module'
        shutil.copytree(MODULE, self.script)

        (self.bin / 'getprop').write_text(
            '#!/bin/sh\n'
            'case "$1" in\n'
            '  service.adb.tls.port) cat "$PROP_TLS" ;;\n'
            '  service.adb.tcp.port) cat "$PROP_TCP" ;;\n'
            '  persist.adb.tcp.port) cat "$PROP_PERSIST" ;;\n'
            '  *) exit 1 ;;\n'
            'esac\n',
            newline='\n',
        )
        (self.bin / 'ss').write_text(
            '#!/bin/sh\n'
            'p=$(cat "$SS_PORT")\n'
            '[ -n "$p" ] || exit 0\n'
            'printf \'LISTEN 0 4 *:%s *:* users:(("adbd",pid=1,fd=16))\\n\' "$p"\n',
            newline='\n',
        )
        (self.bin / 'curl').write_text(
            '#!/bin/sh\nprintf \'%s\\n\' "$*" >>"$CURL_CALLS"\n'
            '[ "$(cat "$CURL_FAIL")" = 0 ]\n',
            newline='\n',
        )
        for path in self.bin.iterdir():
            path.chmod(path.stat().st_mode | stat.S_IEXEC)

        self.env = dict(
            os.environ,
            MOCK_BIN=str(self.bin),
            ADB_PORT_CONF=str(self.conf),
            ADB_PORT_STATE=str(self.state),
            ADB_PORT_LOG=str(self.log),
            ADB_PORT_LOCK=str(self.lock),
            ADB_PORT_PIDFILE=str(self.root / 'pid'),
            PROP_TLS=str(self.prop_tls),
            PROP_TCP=str(self.prop_tcp),
            PROP_PERSIST=str(self.prop_persist),
            SS_PORT=str(self.ss_port),
            CURL_CALLS=str(self.curl_calls),
            CURL_FAIL=str(self.curl_fail),
        )

    def tearDown(self):
        self.temp.cleanup()

    def run_script(self, name, *args):
        return subprocess.run(
            [SHELL, '-c', self.PROLOGUE + 'exec bash "$0" "$@"',
             (self.script / name).as_posix(), *args],
            env=self.env, text=True, capture_output=True, timeout=60,
        )

    def run_lib(self, body):
        return subprocess.run(
            [SHELL, '-c', self.PROLOGUE + f'. "{MODULE.as_posix()}/lib.sh"; {body}'],
            env=self.env, text=True, capture_output=True, timeout=30,
        )

    def configure(self, host='laptop.tailnet', port='8099', token='secret-token'):
        self.conf.write_text(f'HOST={host}\nPORT={port}\nTOKEN={token}\n')
        self.conf.chmod(0o600)


class LibTests(Harness):
    def test_valid_port_bounds(self):
        for value, expected in [('8099', 0), ('1024', 0), ('65535', 0),
                                ('1023', 1), ('65536', 1), ('', 1), ('abc', 1), ('12x', 1)]:
            self.assertEqual(self.run_lib(f'valid_port "{value}"').returncode, expected, value)

    def test_property_preferred_and_ordered(self):
        self.prop_tls.write_text('44627')
        self.prop_tcp.write_text('5555')
        self.assertEqual(self.run_lib('read_port').stdout.strip(), '44627')

    def test_property_falls_back_to_tcp_then_socket(self):
        self.prop_tcp.write_text('5555')
        self.ss_port.write_text('37243')
        self.assertEqual(self.run_lib('read_port').stdout.strip(), '5555')
        self.prop_tcp.write_text('')
        self.assertEqual(self.run_lib('read_port').stdout.strip(), '37243')

    def test_read_port_fails_when_nothing_is_set(self):
        self.assertEqual(self.run_lib('read_port').returncode, 1)

    def test_stop_existing_clears_a_stale_pidfile(self):
        self.assertEqual(self.run_lib('stop_existing').returncode, 0)
        pidfile = self.root / 'pid'
        pidfile.write_text('999999 999998\n')
        r = self.run_lib('stop_existing')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(pidfile.exists())

    def test_line_port_parses_assignment(self):
        cases = [
            ('10-18 23:08:50.692  6564 28033 D AdbDebuggingManager: Received tls port=42597', '42597'),
            ('I AdbDebuggingManager: Received tls port=44659', '44659'),
            ('AdbDebuggingManager: Received tls port=38213 trailing', '38213'),
            ('AdbDebuggingManager: Received tls port=99999', ''),
            ('AdbDebuggingManager: Received tls port=abc', ''),
            ('AdbDebuggingManager: Cannot read system keys', ''),
        ]
        for line, expected in cases:
            self.env['TEST_LINE'] = line
            r = self.run_lib('line_port "$TEST_LINE"')
            self.assertEqual(r.stdout.strip(), expected, line)


class PublishTests(Harness):
    def test_publishes_and_records(self):
        self.configure()
        r = self.run_lib('HOST=a; PORT=1; TOKEN=t; publish 44627')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.state.read_text().strip(), '44627')
        self.assertIn('http://a:1/report/t/44627', self.curl_calls.read_text())

    def test_unchanged_port_is_not_republished(self):
        self.configure()
        self.state.write_text('44627\n')
        r = self.run_lib('HOST=a; PORT=1; TOKEN=t; publish 44627')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.curl_calls.exists())

    def test_forced_publish_republishes_same_port(self):
        self.configure()
        self.state.write_text('44627\n')
        r = self.run_lib('HOST=a; PORT=1; TOKEN=t; publish 44627 1')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('report/t/44627', self.curl_calls.read_text())

    def test_failed_report_keeps_old_state(self):
        self.configure()
        self.state.write_text('11111\n')
        self.curl_fail.write_text('1')
        r = self.run_lib('HOST=a; PORT=1; TOKEN=t; publish 44627')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.state.read_text().strip(), '11111')
        self.assertIn('report failed', self.log.read_text())

    def test_lock_prevents_racing_publishers(self):
        self.configure()
        self.lock.mkdir()
        r = self.run_lib('HOST=a; PORT=1; TOKEN=t; publish 44627')
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.curl_calls.exists())


class ReportTests(Harness):
    def test_report_uses_property(self):
        self.configure()
        self.prop_tls.write_text('44627')
        r = self.run_script('auto.sh', 'report')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.state.read_text().strip(), '44627')
        self.assertIn('report/secret-token/44627', self.curl_calls.read_text())

    def test_report_without_config_does_nothing(self):
        self.prop_tls.write_text('44627')
        r = self.run_script('auto.sh', 'report')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.state.exists())
        self.assertIn('no usable configuration', self.log.read_text())

    def test_status_masks_token_and_shows_current_port(self):
        self.configure(token='tok-123')
        self.prop_tls.write_text('44627')
        self.state.write_text('44627\n')
        out = self.run_script('auto.sh', 'status').stdout
        self.assertIn('laptop.tailnet:8099', out)
        self.assertNotIn('tok-123', out)
        self.assertIn('adbd now: 44627', out)
        self.assertIn('Last published: 44627', out)


class ActionTests(Harness):
    def test_off_disables(self):
        r = self.run_script('action.sh', 'off')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.script / 'disable').exists())
        self.assertIn('Disabled', self.run_script('action.sh', 'status').stdout)

    def test_unknown_action_usage_error(self):
        self.assertEqual(self.run_script('action.sh', 'bogus').returncode, 2)

    def test_disabled_status_satisfies_installer_restoration_check(self):
        # The reviewed installer runs off, then status, and needs this line to
        # accept a module replacement.
        self.assertEqual(self.run_script('action.sh', 'off').returncode, 0)
        out = self.run_script('action.sh', 'status').stdout
        self.assertEqual(out.strip().splitlines()[-1], 'GXR_UPDATE_STATE=STOCK')

    def test_enabled_status_is_not_reported_as_stock(self):
        (self.script / 'disable').unlink()
        out = self.run_script('action.sh', 'status').stdout
        self.assertNotIn('GXR_UPDATE_STATE=STOCK', out)


class PackageTests(Harness):
    def test_shell_syntax(self):
        for script in sorted(MODULE.glob('*.sh')):
            r = subprocess.run([SHELL, '-n', script.as_posix()], text=True, capture_output=True)
            self.assertEqual(r.returncode, 0, f'{script.name}: {r.stderr}')

    def test_layout_is_gxr_compatible(self):
        for path in MODULE.iterdir():
            if path.is_file():
                self.assertNotIn(b'\r', path.read_bytes(), f'{path.name} has CRLF')
        for required in ('module.prop', 'disable', 'skip_mount', 'service.sh',
                         'action.sh', 'auto.sh'):
            self.assertTrue((MODULE / required).exists(), required)
        self.assertEqual((MODULE / 'disable').read_bytes(), b'')
        self.assertEqual((MODULE / 'skip_mount').read_bytes(), b'')

    def test_no_secret_ships_in_the_package(self):
        props = dict(line.split('=', 1)
                     for line in (MODULE / 'module.prop').read_text().splitlines())
        self.assertTrue(props['id'].startswith('gxr_'))
        self.assertGreater(int(props['versionCode']), 1)  # v0.1.1
        for path in MODULE.iterdir():
            if path.is_file():
                text = path.read_text(errors='ignore')
                self.assertIsNone(re.search(r'\b[a-zA-Z0-9-]+\.ts\.net\b', text), path.name)
                self.assertIsNone(re.search(r'\b[0-9a-f]{32}\b', text), path.name)

    def test_reproducible_disabled_package_and_checksums(self):
        from tools.build_adb_port import build
        first = build()
        digest = hashlib.sha256(first.read_bytes()).hexdigest()
        build()
        self.assertEqual(digest, hashlib.sha256(first.read_bytes()).hexdigest())
        self.assertTrue(first.name.endswith('-disabled.zip'))
        with ZipFile(first) as archive:
            names = archive.namelist()
            self.assertEqual(archive.read('disable'), b'')
            self.assertEqual(archive.read('skip_mount'), b'')
            for required in ('action.sh', 'service.sh', 'auto.sh'):
                self.assertIn(required, names)
            self.assertEqual(len(archive.read('SHA256SUMS').decode().splitlines()),
                             len(names) - 2)
            for line in archive.read('SHA256SUMS').decode().splitlines():
                checksum, name = line.split('  ')
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), checksum, name)


if __name__ == '__main__':
    unittest.main()
