"""Reproducible local-only experimental module package; no public update feed."""
import hashlib
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def build():
    source = ROOT / 'modules/xbox-unknown-key'
    payload = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
    assert payload['disable'] == payload['skip_mount'] == b''
    assert all(b'\r' not in value for value in payload.values())
    payload['SHA256SUMS'] = ''.join(
        f'{hashlib.sha256(value).hexdigest()}  {name}\n'
        for name, value in sorted(payload.items()) if name != 'disable'
    ).encode()
    out = ROOT / 'dist/gxr-bsvr-xbox-unknown-key-0.1.0-disabled.zip'
    out.parent.mkdir(exist_ok=True)
    with ZipFile(out, 'w', compression=ZIP_DEFLATED) as z:
        for name, value in sorted(payload.items()):
            info = ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            z.writestr(info, value)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_suffix('.zip.sha256').write_text(f'{digest}  {out.name}\n', newline='\n')
    print(out)
    print(digest)
    return out


if __name__ == '__main__':
    build()
