import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "modules/usb-compat"
SHELL = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else shutil.which("sh")


class UsbModuleTests(unittest.TestCase):
    def run_mock(self, body):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, LIB=(SOURCE / "lib.sh").as_posix(), TEST_STATE=Path(directory).as_posix())
            setup = r'''
set -eu
. "$LIB"
STATE="$TEST_STATE"
if command -v cygpath >/dev/null 2>&1; then STATE=$(cygpath -u "$STATE"); fi
MODDIR="$STATE/module"
GADGET="$STATE/gadget"
mkdir -p "$MODDIR" "$GADGET/functions/ncm.gs6"
log() { :; }
compatible() { return 0; }
RECORD=''
mount_record() { printf '%s\n' "$RECORD"; }
MODE=mtp
svc() {
  test "$1" = usb
  case "$2" in
    getFunctions) printf '%s\n' "$MODE" >&2 ;;
    setFunctions) printf '%s\n' "${3:-none}" >> "$STATE/calls" ;;
    *) return 1 ;;
  esac
}
'''
            result = subprocess.run([SHELL, "-c", setup + body], env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_preserves_accessory_and_explicit_modes(self):
        self.run_mock('''
for MODE in accessory accessory,adb accessory,audio_source rndis ptp midi ncm unexpected; do
  select_ncm
  test ! -e "$STATE/calls"
  test ! -e "$STATE/selected-ncm"
done
''')

    def test_requests_ncm_from_mtp_or_charging(self):
        self.run_mock('''
for MODE in mtp none ''; do
  select_ncm
  test "$(cat "$STATE/calls")" = ncm
  test "$(cat "$STATE/prior-functions")" = "$MODE"
  test -f "$STATE/selected-ncm"
  rm "$STATE/calls" "$STATE/prior-functions" "$STATE/selected-ncm"
done
''')

    def test_repeated_selection_preserves_original_mode(self):
        self.run_mock('''
MODE=mtp; select_ncm
MODE=none; select_ncm
test "$(cat "$STATE/prior-functions")" = mtp
''')

    def test_disabled_and_removed_prevent_activation(self):
        self.run_mock('''
enabled
touch "$MODDIR/disable"
if enabled; then exit 1; fi
rm "$MODDIR/disable"
touch "$MODDIR/remove"
if enabled; then exit 1; fi
''')

    def test_foreign_overlay_refused(self):
        self.run_mock('''
RECORD=/foreign/overlay.xml
nsenter() { echo 'must not enter namespace' >&2; exit 99; }
if apply_aoa; then exit 1; fi
''')

    def test_owned_overlay_is_idempotent(self):
        self.run_mock('''
RECORD=$(our_mount_root)
nsenter() { echo 'must not mount twice' >&2; exit 99; }
apply_aoa
''')

    def test_unsupported_firmware_refused(self):
        self.run_mock('''
compatible() { return 1; }
nsenter() { echo 'must not enter namespace' >&2; exit 99; }
if apply_aoa; then exit 1; fi
if prepare_ncm; then exit 1; fi
test ! -d "$GADGET/functions/ncm.0"
''')

    def test_original_hash_mismatch_refused(self):
        self.run_mock('''
nsenter() {
  test "$3" = sha256sum
  echo "wrong-hash  $TARGET"
}
chcon() { echo 'must not relabel or mount' >&2; exit 99; }
if apply_aoa; then exit 1; fi
''')

    def test_ncm_preparation_is_idempotent_and_owned(self):
        self.run_mock('''
prepare_ncm
test -d "$GADGET/functions/ncm.0"
test -f "$STATE/created-ncm"
prepare_ncm
''')

    def test_preexisting_ncm_function_is_not_claimed(self):
        self.run_mock('''
mkdir "$GADGET/functions/ncm.0"
prepare_ncm
test ! -e "$STATE/created-ncm"
''')

    def test_rollback_preserves_accessory_and_unowned_mode(self):
        self.run_mock('''
touch "$STATE/selected-ncm"
echo mtp > "$STATE/prior-functions"
MODE=accessory
rollback
test ! -e "$STATE/calls"
MODE=ncm
rollback
test ! -e "$STATE/calls"
''')

    def test_rollback_restores_previous_mode(self):
        self.run_mock('''
for prior in mtp none ''; do
  touch "$STATE/selected-ncm"
  printf '%s\n' "$prior" > "$STATE/prior-functions"
  MODE=ncm
  rollback
  test "$(cat "$STATE/calls")" = "${prior:-none}"
  test ! -e "$STATE/selected-ncm"
  rm "$STATE/calls"
done
''')

    def test_invalid_recovery_record_is_retained(self):
        self.run_mock('''
touch "$STATE/selected-ncm"
echo unexpected > "$STATE/prior-functions"
MODE=ncm
if rollback; then exit 1; fi
test -f "$STATE/selected-ncm"
test ! -e "$STATE/calls"
''')

    def test_shell_syntax(self):
        for script in SOURCE.glob("*.sh"):
            with self.subTest(script=script.name):
                result = subprocess.run([SHELL, "-n", script.as_posix()], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)


class UsbPackagingTests(unittest.TestCase):
    def test_accessory_xml_preserves_library_declaration(self):
        root = ET.parse(SOURCE / "aoa.xml").getroot()
        self.assertEqual(root.tag, "permissions")
        self.assertEqual(len(root), 2)
        self.assertEqual(root.find("feature").attrib, {"name": "android.hardware.usb.accessory"})
        self.assertEqual(root.find("library").attrib, {
            "name": "com.android.future.usb.accessory",
            "file": "/system/framework/com.android.future.usb.accessory.jar",
        })

    def test_reproducible_disabled_package(self):
        from tools.build_usb import FILES, build
        first = build()
        digest = hashlib.sha256(first.read_bytes()).hexdigest()
        build()
        self.assertEqual(digest, hashlib.sha256(first.read_bytes()).hexdigest())
        self.assertEqual(first.with_suffix(".zip.sha256").read_text().split()[0], digest)
        with ZipFile(first) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()), set(FILES) | {"SHA256SUMS"})
            self.assertEqual(archive.read("disable"), b"")
            self.assertEqual(archive.read("skip_mount"), b"")
            checksummed = set()
            for line in archive.read("SHA256SUMS").decode().splitlines():
                expected, name = line.split("  ")
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), expected)
                checksummed.add(name)
            self.assertEqual(checksummed, set(FILES))
            for item in archive.infolist():
                self.assertNotIn(b"\r", archive.read(item))
                self.assertEqual((item.external_attr >> 16) & 0o170000, 0o100000)
            self.assertEqual((archive.getinfo("aoa.xml").external_attr >> 16) & 0o777, 0o444)
