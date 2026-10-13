"""Build a reproducible disabled GXR module and its update feed."""
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]


def build():
    source = ROOT / "modules/auto-spatialization"
    props = dict(line.split("=", 1) for line in (source / "module.prop").read_text().splitlines())
    version = props["version"]
    name = f"gxr-bsvr-auto-spatialization-{version}-auto.zip"
    payload = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
    assert payload["disable"] == payload["skip_mount"] == b""
    assert all(b"\r" not in data for data in payload.values())
    payload["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n"
        for name, data in sorted(payload.items()) if name != "disable"
    ).encode()
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    path = dist / name
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for filename, data in sorted(payload.items()):
            info = ZipInfo(filename, (2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100755 if filename.endswith(".sh") else 0o100644) << 16
            archive.writestr(info, data)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (dist / (name + ".sha256")).write_text(f"{digest}  {name}\n", newline="\n")
    updates = ROOT / "updates"
    updates.mkdir(exist_ok=True)
    feed = {
        "version": version, "versionCode": int(props["versionCode"]),
        "zipUrl": f"https://github.com/BlueScorpioVR/galaxyxr-modules/releases/download/auto-spatialization/v{version}/{name}",
        "changelog": "https://raw.githubusercontent.com/BlueScorpioVR/galaxyxr-modules/main/changelogs/auto-spatialization.md",
        "sha256": digest,
    }
    (updates / "auto-spatialization.json").write_text(json.dumps(feed, indent=2) + "\n", newline="\n")
    print(path)
    print(digest)
    return path


if __name__ == "__main__":
    build()
