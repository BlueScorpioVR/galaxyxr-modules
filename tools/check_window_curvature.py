"""Compile and run the dependency-free curvature safety tests with Java 8 output."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", required=True, type=Path)
    parser.add_argument("--ecj", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.java, args.ecj):
        if not path.is_file():
            parser.error(f"Missing build dependency: {path}")
    sources = sorted((ROOT / "modules/window-curvature/java").rglob("*.java"))
    sources.append(ROOT / "tests/WindowCurvatureLeaseTest.java")
    sources.append(ROOT / "tests/WindowCurvatureTransactionTest.java")
    sources.append(ROOT / "tests/WindowCurvatureMenuBoundsTest.java")
    sources.extend(sorted((ROOT / "tests/window-curvature-mocks").rglob("*.java")))
    with tempfile.TemporaryDirectory(prefix="gxr-curvature-check-") as output:
        subprocess.run([
            str(args.java), "-jar", str(args.ecj), "-source", "1.8", "-target", "1.8",
            "-proc:none", "-failOnWarning", "-d", output,
            *(str(path) for path in sources),
        ], check=True)
        subprocess.run([str(args.java), "-cp", output, "WindowCurvatureLeaseTest"], check=True)
        subprocess.run([str(args.java), "-cp", output, "WindowCurvatureTransactionTest"], check=True)
        subprocess.run([str(args.java), "-cp", output, "WindowCurvatureMenuBoundsTest"], check=True)


if __name__ == "__main__":
    main()
