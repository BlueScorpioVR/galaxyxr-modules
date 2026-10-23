"""Offline ZIP integrity/layout check; not a claim of runtime compatibility."""
import argparse
import hashlib
import json
import re
from pathlib import PurePosixPath
from zipfile import ZipFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip')
    args = parser.parse_args()
    with ZipFile(args.zip) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)), 'Duplicate entries'
        assert all(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts for name in names)
        assert archive.testzip() is None
        assert archive.read('disable') == archive.read('skip_mount') == b''
        assert len(names) <= 128 and sum(info.file_size for info in archive.infolist()) <= 64 * 1024 * 1024
        for name in names:
            assert re.fullmatch(r'[A-Za-z0-9._/-]+', name), name
            assert '/' not in name or name.startswith(('bin/', 'webroot/')), name
        for name in ('customize.sh', 'service.sh', 'action.sh', 'auto.sh', 'control.sh', 'uninstall.sh', 'bin/frida-inject'):
            assert (archive.getinfo(name).external_attr >> 16) & 0o111, name
        assert not any('mocks' in name or 'frida-server' in name or name.startswith('system/') for name in names)
        assert archive.read('bin/classes.dex').startswith(b'dex\n')
        elf = archive.read('bin/frida-inject')
        assert elf[:4] == b'\x7fELF' and int.from_bytes(elf[18:20], 'little') == 183
        receipt = json.loads(archive.read('build.json'))
        assert receipt['frida'] == '17.23.3'
        assert hashlib.sha256(elf).hexdigest() == receipt['injectorSha256']
        checked = set()
        for line in archive.read('SHA256SUMS').decode().splitlines():
            digest, name = line.split('  ', 1)
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest, name
            checked.add(name)
        assert checked == set(names) - {'SHA256SUMS', 'disable'}
        assert {'action.sh', 'auto.sh', 'module.prop'} <= checked
        for line in archive.read('firmware.sha256').decode().splitlines():
            digest, path = line.split('  ', 1)
            assert len(digest) == 64 and path.startswith('/system_ext/')
        assert len(archive.read('bin/licenses/frida-COPYING')) > 1000
        assert len(archive.read('bin/licenses/LGPL-2.0-or-later.txt')) > 20000
        assert b'--eternalize' not in archive.read('control.sh')
    print('PASS: disabled ZIP, executable modes, manifest, ARM64/Dex, sources/licenses, firmware pins')


if __name__ == '__main__':
    main()
