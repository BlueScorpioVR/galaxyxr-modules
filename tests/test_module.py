import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SHELL = ("C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else shutil.which("sh"))


class ModuleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.module = self.base / "module"
        shutil.copytree(ROOT / "modules/auto-spatialization", self.module)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.value = self.base / "value"
        self.value.write_text("0\n")
        (self.bin / "getprop").write_text('#!/bin/sh\nprintf "%s\\n" "${BOOT_COMPLETE:-1}"\n', newline="\n")
        (self.bin / "settings").write_text('''#!/bin/sh
set -eu
test "$1" = --user && test "$2" = 0
test "$4" = system
test "$5" = auto_spatialization_settings
case "$3" in
 get) if [ -f "$MOCK_VALUE" ]; then cat "$MOCK_VALUE"; else echo null; fi ;;
 put) [ "${FAIL_WRITE:-0}" = 0 ] || exit 1; echo "$6" > "$MOCK_VALUE" ;;
 delete) rm -f "$MOCK_VALUE" ;;
 *) exit 1 ;;
esac
''', newline="\n")
        # CLI: settings --user 0 <operation> system <key> [value].
        for p in self.bin.iterdir():
            p.chmod(0o755)
        self.env = dict(os.environ, MOCK_VALUE=self.value.as_posix())

    def tearDown(self):
        self.temp.cleanup()

    def run_action(self, operation, **environment):
        env = dict(self.env, **environment)
        command = 'export PATH="$MOCK_BIN:$PATH"; exec sh "$MODULE_SCRIPT" "$OPERATION"'
        if os.name == "nt":
            command = 'export PATH="$(cygpath -u "$MOCK_BIN"):$PATH"; exec sh "$MODULE_SCRIPT" "$OPERATION"'
        env.update(MOCK_BIN=self.bin.as_posix(), MODULE_SCRIPT=(self.module / "auto.sh").as_posix(), OPERATION=operation)
        return subprocess.run([SHELL, "-c", command], env=env, capture_output=True, text=True, timeout=15)

    def enable(self):
        (self.module / "disable").unlink()

    def test_disabled_does_not_write(self):
        result = self.run_action("apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.value.read_text().strip(), "0")
        self.assertFalse((self.module / "original-value").exists())

    def test_apply_and_restore(self):
        self.enable()
        result = self.run_action("apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.value.read_text().strip(), "1")
        self.assertEqual((self.module / "original-value").read_text().strip(), "0")
        self.assertNotIn("GXR_UPDATE_STATE=STOCK", self.run_action("status").stdout)
        self.assertEqual(self.run_action("off").returncode, 0)
        self.assertEqual(self.value.read_text().strip(), "0")
        self.assertIn("GXR_UPDATE_STATE=STOCK", self.run_action("status").stdout)

    def test_repeated_start_preserves_original(self):
        self.enable()
        self.assertEqual(self.run_action("apply").returncode, 0)
        self.assertEqual(self.run_action("apply").returncode, 0)
        self.assertEqual((self.module / "original-value").read_text().strip(), "0")

    def test_absent_setting_restored(self):
        self.value.unlink()
        self.enable()
        self.assertEqual(self.run_action("apply").returncode, 0)
        self.assertEqual(self.run_action("off").returncode, 0)
        self.assertFalse(self.value.exists())

    def test_later_user_choice_preserved(self):
        self.value.write_text("1\n")
        self.enable()
        self.assertEqual(self.run_action("apply").returncode, 0)
        self.value.write_text("0\n")
        self.assertEqual(self.run_action("off").returncode, 0)
        self.assertEqual(self.value.read_text().strip(), "0")

    def test_failed_write_keeps_recovery(self):
        self.enable()
        self.assertNotEqual(self.run_action("apply", FAIL_WRITE="1").returncode, 0)
        self.assertTrue((self.module / "original-value").exists())

    def test_unexpected_value_refused(self):
        self.value.write_text("unexpected\n")
        self.enable()
        self.assertNotEqual(self.run_action("apply").returncode, 0)
        self.assertEqual(self.value.read_text().strip(), "unexpected")

    def test_shell_syntax(self):
        for script in self.module.glob("*.sh"):
            result = subprocess.run([SHELL, "-n", script.as_posix()], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


class PackagingTests(unittest.TestCase):
    def test_reproducible_package_and_feed(self):
        from tools.build import build
        first = build()
        digest = hashlib.sha256(first.read_bytes()).hexdigest()
        build()
        self.assertEqual(digest, hashlib.sha256(first.read_bytes()).hexdigest())
        feed = json.loads((ROOT / "updates/auto-spatialization.json").read_text())
        self.assertEqual(feed["sha256"], digest)
        with ZipFile(first) as z:
            self.assertEqual(z.read("disable"), b"")
            self.assertEqual(z.read("skip_mount"), b"")
            for line in z.read("SHA256SUMS").decode().splitlines():
                checksum, name = line.split("  ")
                self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(), checksum)
            self.assertFalse(any(n.startswith("system/") for n in z.namelist()))
