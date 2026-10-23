"""Build the temporary Android helper only, not an installable KernelSU ZIP."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("java", "ecj", "r8", "android-jar", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    dependencies = {name: getattr(args, name) for name in ("java", "ecj", "r8", "android_jar")}
    for name, path in dependencies.items():
        if not path.is_file():
            parser.error(f"Missing {name}: {path}")
    module = ROOT / "modules/window-curvature"
    sources = sorted((module / "java").rglob("*.java")) + sorted((module / "android").rglob("*.java"))
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gxr-menu-build-") as temporary:
        directory = Path(temporary)
        classes = directory / "classes"
        classes.mkdir()
        subprocess.run([
            str(args.java), "-jar", str(args.ecj), "-source", "1.8", "-target", "1.8",
            "-proc:none", "-failOnWarning", "-classpath", str(args.android_jar),
            "-d", str(classes), *(str(path) for path in sources),
        ], check=True)
        archive = directory / "helper.jar"
        with ZipFile(archive, "w", ZIP_DEFLATED) as output:
            for path in sorted(classes.rglob("*.class")):
                output.write(path, path.relative_to(classes).as_posix())
        subprocess.run([
            str(args.java), "-cp", str(args.r8), "com.android.tools.r8.D8",
            "--min-api", "26", "--lib", str(args.android_jar),
            "--output", str(args.output), str(archive),
        ], check=True)
    dex = args.output / "classes.dex"
    receipt = {
        "kind": "temporary-android-helper-not-module",
        "dependencies": {name: {"path": str(path.resolve()),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for name, path in dependencies.items()},
        "sources": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources},
        "dexSha256": hashlib.sha256(dex.read_bytes()).hexdigest(),
    }
    (args.output / "build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"Helper DEX built: {len(dex.read_bytes())} bytes; no device changes")


if __name__ == "__main__":
    main()
