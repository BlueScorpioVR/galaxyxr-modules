"""Reproducible, disabled, direct-deployment USB module (no update feed)."""
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "README.md", "action.sh", "aoa.xml", "customize.sh", "disable", "lib.sh",
    "module.prop", "post-fs-data.sh", "service.sh", "skip_mount", "uninstall.sh",
)


def build():
    source = ROOT / "modules/usb-compat"
    props = dict(line.split("=", 1) for line in (source / "module.prop").read_text().splitlines())
    assert props["id"] == "gxr-usb-compat"
    name = f"gxr-usb-compat-{props['version']}.zip"
    payload = {name: (source / name).read_bytes() for name in FILES}
    assert payload["disable"] == payload["skip_mount"] == b""
    assert all(b"\r" not in data for data in payload.values())
    payload["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n"
        for name, data in sorted(payload.items())
    ).encode()
    out = ROOT / "dist" / name
    out.parent.mkdir(exist_ok=True)
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
        for filename, data in sorted(payload.items()):
            info = ZipInfo(filename, (2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = ZIP_DEFLATED
            mode = 0o100755 if filename.endswith(".sh") else 0o100644
            if filename == "aoa.xml":
                mode = 0o100444
            info.external_attr = mode << 16
            archive.writestr(info, data)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_suffix(".zip.sha256").write_text(f"{digest}  {out.name}\n", newline="\n")
    print(out)
    print(digest)
    return out


if __name__ == "__main__":
    build()
