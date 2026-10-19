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
    """Runs the module scripts with mock `ss`/`curl` on PATH."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.conf = self.root / 'conf'
        self.state = self.root / 'state'
        self.log = self.root / 'log'
        self.curl_calls = self.root / 'curl-calls'
        self.curl_fail = self.root / 'curl-fail'
        self.ss_port = self.root / 'ss-port'
        self.ss_port.write_text('')
        self.curl_fail.write_text('0')
        self.script = self.root / 'module'
        shutil.copytree(MODULE, self.script)
        # The mock prints the socket line only when a port has been staged.
        (self.bin / 'ss').write_text(
            '#!/bin/sh\n'
            'p=$(cat "$SS_PORT")\n'
            '[ -n "$p" ] || exit 0\n'
            'printf \'LISTEN 0 4 *:%s *:* users:(("adbd",pid=6843,fd=16))\\n\' "$p"\n',
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
            ADB_PORT_MAX_TRIES='2',
            ADB_PORT_INTERVAL='0',
            CURL_CALLS=str(self.curl_calls),
            SS_PORT=str(self.ss_port),
            CURL_FAIL=str(self.curl_fail),
        )

    # MSYS would otherwise prefer the real /mingw64/bin/curl, and the mock files
    # are Windows paths; convert everything to POSIX form inside the shell.
    PROLOGUE = (
        'export PATH="$(cygpath -u "$MOCK_BIN"):$PATH"; '
        'for v in ADB_PORT_CONF ADB_PORT_STATE ADB_PORT_LOG CURL_CALLS SS_PORT CURL_FAIL; do '
        'eval "export $v=\\$(cygpath -u \\"\\$$v\\")"; done; '
    )

    def tearDown(self):
        self.temp.cleanup()

    def run_script(self, name, *args):
        return subprocess.run(
            [SHELL, '-c', self.PROLOGUE + 'exec bash "$0" "$@"',
             (self.script / name).as_posix(), *args],
            env=self.env, text=True, capture_output=True, timeout=30,
        )

    def run_lib(self, body):
        return subprocess.run(
            [SHELL, '-c', self.PROLOGUE + f'. "{MODULE.as_posix()}/lib.sh"; {body}'],
            env=self.env, text=True, capture_output=True, timeout=15,
        )

    def configure(self, host='laptop.tailnet', port='8099', token='secret-token'):
        self.conf.write_text(f'HOST={host}\nPORT={port}\nTOKEN={token}\n')
        self.conf.chmod(0o600)


class LibTests(Harness):
    def test_valid_port_bounds(self):
        for value, expected in [('8099', 0), ('1024', 0), ('65535', 0),
                                ('1023', 1), ('65536', 1), ('', 1), ('abc', 1), ('12x', 1)]:
            self.assertEqual(self.run_lib(f'valid_port "{value}"').returncode, expected, value)

    def test_adb_port_reads_adbd_socket(self):
        for port in ('37243', '45541'):
            self.ss_port.write_text(port)
            self.assertEqual(self.run_lib('adb_port').stdout.strip(), port)

    def test_adb_port_empty_without_adbd(self):
        self.assertEqual(self.run_lib('adb_port').stdout.strip(), '')

    def test_load_conf_requires_every_field(self):
        self.assertEqual(self.run_lib('load_conf').returncode, 1)
        self.configure()
        self.assertEqual(
            self.run_lib('load_conf; echo "$HOST $PORT $TOKEN"').stdout.strip(),
            'laptop.tailnet 8099 secret-token',
        )

    def test_write_conf_round_trip_excludes_others(self):
        r = self.run_lib('write_conf laptop.tailnet 8099 tok-123; load_conf; echo "$HOST $PORT $TOKEN"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), 'laptop.tailnet 8099 tok-123')

    def test_redact_hides_token(self):
        out = self.run_lib('redact secret-token').stdout
        self.assertNotIn('ecret', out)
        self.assertIn('12 characters', out)


class PublishTests(Harness):
    def test_reports_and_records_port(self):
        self.configure()
        self.ss_port.write_text('37243')
        r = self.run_script('auto.sh', 'report')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.state.read_text().strip(), '37243')
        self.assertIn('http://laptop.tailnet:8099/report/secret-token/37243',
                      self.curl_calls.read_text())
        self.assertIn('published adbd port 37243', self.log.read_text())

    def test_unreachable_host_exits_zero_without_state(self):
        self.configure()
        self.ss_port.write_text('37243')
        self.curl_fail.write_text('1')
        r = self.run_script('auto.sh', 'report')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.state.exists())
        self.assertIn('not published this generation', self.log.read_text())

    def test_no_config_is_quiet_and_succeeds(self):
        self.ss_port.write_text('37243')
        r = self.run_script('auto.sh', 'report')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.curl_calls.exists())
        self.assertIn('no usable configuration', self.log.read_text())

    def test_invalid_port_never_reported(self):
        self.configure()
        for bad in ('', '80', 'abc'):
            self.ss_port.write_text(bad)
            self.curl_calls.unlink(missing_ok=True)
            r = self.run_script('auto.sh', 'report')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(self.curl_calls.exists(), bad)

    def test_service_skips_when_disabled_or_removed(self):
        self.configure()
        self.ss_port.write_text('37243')
        for marker in ('disable', 'remove'):
            (self.script / marker).write_text('')
            r = self.run_script('service.sh')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(self.state.exists(), marker)
            (self.script / marker).unlink()


class ActionTests(Harness):
    def test_off_disables_and_status_reports_it(self):
        r = self.run_script('action.sh', 'off')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.script / 'disable').exists())
        status = self.run_script('action.sh', 'status')
        self.assertIn('Disabled', status.stdout)

    def test_status_masks_token_and_shows_last_port(self):
        self.configure(token='tok-123')
        self.state.write_text('37243\n')
        out = self.run_script('action.sh', 'status').stdout
        self.assertIn('laptop.tailnet:8099', out)
        self.assertNotIn('tok-123', out)
        self.assertIn('37243', out)

    @unittest.skipIf(hasattr(os, 'geteuid') and os.geteuid() == 0, 'host is root')
    def test_report_requires_root(self):
        self.configure()
        self.ss_port.write_text('45541')
        r = self.run_script('action.sh', 'report')
        self.assertEqual(r.returncode, 1)
        self.assertIn('root required', r.stdout)

    def test_unknown_action_usage_error(self):
        self.assertEqual(self.run_script('action.sh', 'bogus').returncode, 2)


class PackageTests(Harness):
    def test_shell_syntax(self):
        for script in sorted(MODULE.glob('*.sh')):
            r = subprocess.run([SHELL, '-n', script.as_posix()], text=True, capture_output=True)
            self.assertEqual(r.returncode, 0, f'{script.name}: {r.stderr}')

    def test_layout_is_gxr_compatible(self):
        for path in MODULE.iterdir():
            if path.is_file():
                self.assertNotIn(b'\r', path.read_bytes(), f'{path.name} has CRLF')
        # KernelSU's reviewed installer verifies the installed module, so these
        # must exist and be listed in SHA256SUMS.
        for required in ('module.prop', 'disable', 'skip_mount', 'service.sh',
                         'action.sh', 'auto.sh'):
            self.assertTrue((MODULE / required).exists(), required)
        self.assertEqual((MODULE / 'disable').read_bytes(), b'')
        self.assertEqual((MODULE / 'skip_mount').read_bytes(), b'')
        sums = (MODULE / 'SHA256SUMS').read_text() if (MODULE / 'SHA256SUMS').exists() else ''
        for required in ('action.sh', 'auto.sh', 'module.prop'):
            self.assertTrue(required in sums or not (MODULE / 'SHA256SUMS').exists(), required)

    def test_no_secret_ships_in_the_package(self):
        props = dict(line.split('=', 1)
                     for line in (MODULE / 'module.prop').read_text().splitlines())
        self.assertTrue(props['id'].startswith('gxr_'))
        self.assertGreater(int(props['versionCode']), 0)
        for path in MODULE.iterdir():
            if path.is_file():
                text = path.read_text(errors='ignore')
                # No hard-coded tailnet host and no literal 32-hex token.
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
            self.assertIn('action.sh', names)
            self.assertIn('service.sh', names)
            self.assertIn('auto.sh', names)
            # KernelSU's reviewed installer requires exactly: every file minus
            # `disable` minus `SHA256SUMS` itself.  sums + 2 == total files.
            self.assertEqual(len(archive.read('SHA256SUMS').decode().splitlines()),
                             len(names) - 2)
            for line in archive.read('SHA256SUMS').decode().splitlines():
                checksum, name = line.split('  ')
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), checksum, name)


if __name__ == '__main__':
    unittest.main()
