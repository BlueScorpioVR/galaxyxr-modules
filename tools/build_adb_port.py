"""Reproducible local-only module package; no public update feed.

The publisher ships no host, port or token: configure it on the device after
install (see the module README). That is why there is no update feed here.
"""
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]


def build():
    source = ROOT / 'modules/adb-port-publisher'
    props = dict(
        line.split('=', 1) for line in (source / 'module.prop').read_text().splitlines()
    )
    name = f"gxr-bsvr-adb-port-publisher-{props['version']}-disabled.zip"
    payload = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
    assert payload['disable'] == payload['skip_mount'] == b''
    assert all(b'\r' not in value for value in payload.values())
    payload['SHA256SUMS'] = ''.join(
        f'{hashlib.sha256(value).hexdigest()}  {filename}\n'
        for filename, value in sorted(payload.items()) if filename != 'disable'
    ).encode()
    out = ROOT / 'dist' / name
    out.parent.mkdir(exist_ok=True)
    with ZipFile(out, 'w', compression=ZIP_DEFLATED) as archive:
        for filename, value in sorted(payload.items()):
            info = ZipInfo(filename, (2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = ZIP_DEFLATED
            info.external_attr = (0o100755 if filename.endswith('.sh') else 0o100644) << 16
            archive.writestr(info, value)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_suffix('.zip.sha256').write_text(f'{digest}  {out.name}\n', newline='\n')
    print(out)
    print(digest)
    return out


if __name__ == '__main__':
    build()
