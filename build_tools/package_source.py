"""Package the public source tree, excluding environments, caches and user data."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    "README.md", "LICENSE", "LICENSE.txt", "VALIDATION.md", "CONTRIBUTING.md",
    "CHANGELOG.md", "RELEASE_NOTES.md", "SECURITY.md", "WINDOWS_ACCEPTANCE_PROMPT.txt",
    "requirements-windows.txt", "package.json", "package-lock.json",
    ".gitignore", ".gitattributes",
}
SOURCE_DIRS = {"app", "docs", "tests", ".github"}
VALIDATION_FILES = {"english-linux-self-test.json", "english-example-qa.json"}
BUILD_FILES = {
    "launcher.c", "RiverLakeCartography.exe", "launcher-build.json",
    "assemble_windows.py", "build_windows.ps1", "build_windows.cmd",
    "WINDOWS_ACCEPTANCE.md", "requirements-runtime.lock.txt", "runtime-wheels.json",
    "windows_build_validation.json", "pe_dependencies.json", "package_source.py", "fetch_font.py",
}
EXCLUDED_PARTS = {"__pycache__", "node_modules", ".venv", "live_xuanwu", "local", "ci"}


def source_files():
    for name in sorted(ROOT_FILES):
        path = ROOT / name
        if path.is_file():
            yield path
    for name in sorted(SOURCE_DIRS):
        directory = ROOT / name
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if (path.is_file() and not EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts)
                    and path.suffix not in {".pyc", ".pyo", ".log", ".tmp"}):
                yield path
    for name in sorted(BUILD_FILES):
        path = ROOT / "build_tools" / name
        if path.is_file():
            yield path
    for name in sorted(VALIDATION_FILES):
        path = ROOT / "validation" / name
        if path.is_file():
            yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "RiverLakeCartography-Source.zip")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in source_files():
            archive.write(path, Path("RiverLakeCartography-Source") / path.relative_to(ROOT))
            count += 1
    with zipfile.ZipFile(args.output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Source ZIP failed its CRC check")
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(json.dumps({"file": str(args.output), "files": count,
                      "bytes": args.output.stat().st_size, "sha256": digest}))


if __name__ == "__main__":
    main()
