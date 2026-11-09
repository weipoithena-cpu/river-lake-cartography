"""Assemble an actual Windows x86-64 portable app, on any build OS.

This is not a PyInstaller cross-build. The executable is a native PE launcher,
and every binary Python dependency comes from the Windows CPython 3.14 wheel.
The private interpreter is Python.org's embeddable Windows distribution.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import urllib.request
import zipfile
from fetch_font import fetch_font

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
APP_VERSION = "1.0.0-preview.1"
PYTHON_VERSION = "3.14.10"
PYTHON_URL = "https://www.python.org/ftp/python/3.14.10/python-3.14.10-embed-amd64.zip"
PYTHON_SHA256 = "90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def download(url: str, path: Path, expected: str) -> None:
    if path.exists() and digest(path) == expected:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".download")
    request = urllib.request.Request(url, headers={"User-Agent": "RiverLakeCartography-build/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response, temp.open("wb") as output:
        shutil.copyfileobj(response, output)
    if digest(temp) != expected:
        temp.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded file checksum mismatch: {path.name}")
    temp.replace(path)


def verify_launcher(path: Path) -> dict:
    data = path.read_bytes()
    if data[:2] != b"MZ":
        raise RuntimeError("Launcher is not a Windows executable")
    offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[offset:offset + 4] != b"PE\0\0":
        raise RuntimeError("Invalid PE header")
    machine = struct.unpack_from("<H", data, offset + 4)[0]
    subsystem = struct.unpack_from("<H", data, offset + 24 + 68)[0]
    if machine != 0x8664 or subsystem != 2:
        raise RuntimeError(f"Expected AMD64 GUI launcher, found {machine:#x}/{subsystem}")
    record = json.loads((TOOLS / "launcher-build.json").read_text(encoding="utf-8"))
    if digest(path) != record["launcher_sha256"] or digest(TOOLS / "launcher.c") != record["source_sha256"]:
        raise RuntimeError("Launcher source/binary hashes differ from launcher-build.json; recompile and record both hashes")
    return {"format": "PE32+", "machine": "AMD64", "subsystem": "Windows GUI", "sha256": digest(path),
            "source_sha256": record["source_sha256"], "compiler": record["compiler"]}


def install_wheel(wheel: Path, runtime: Path, packages: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        for item in archive.infolist():
            parts = Path(item.filename).parts
            if not parts or item.is_dir():
                continue
            if item.filename.startswith("/") or ".." in parts:
                raise RuntimeError("Unsafe wheel path")
            if parts[0].endswith(".data"):
                category = parts[1]
                if category in ("purelib", "platlib"):
                    destination = packages.joinpath(*parts[2:])
                elif category == "data":
                    destination = runtime.joinpath(*parts[2:])
                else:
                    continue  # Build headers and console-entry wrappers are not used.
            else:
                destination = packages.joinpath(*parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)


def assemble(destination: Path, create_zip: bool = False) -> Path:
    fetch_font()
    cache = TOOLS / "downloads"
    embed = cache / PYTHON_URL.rsplit("/", 1)[-1]
    download(PYTHON_URL, embed, PYTHON_SHA256)
    records = json.loads((TOOLS / "runtime-wheels.json").read_text(encoding="utf-8"))
    wheels = cache / "wheels"
    if any(not (wheels / item["file"]).is_file() for item in records):
        wheels.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            sys.executable, "-m", "pip", "download", "--platform", "win_amd64",
            "--python-version", "3.14", "--implementation", "cp", "--abi", "cp314",
            "--only-binary=:all:", "--require-hashes", "--dest", str(wheels),
            "-r", str(TOOLS / "requirements-runtime.lock.txt")
        ], check=True)
    for item in records:
        if digest(wheels / item["file"]) != item["sha256"]:
            raise RuntimeError("Wheel checksum mismatch: " + item["file"])
    launcher = TOOLS / "RiverLakeCartography.exe"
    launcher_info = verify_launcher(launcher)
    if not (ROOT / "app" / "main.py").is_file():
        raise RuntimeError("Application entry point app/main.py is missing")
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    runtime = destination / "runtime"
    runtime.mkdir(exist_ok=True)
    with zipfile.ZipFile(embed) as archive:
        archive.extractall(runtime)
    packages = runtime / "Lib" / "site-packages"
    packages.mkdir(parents=True, exist_ok=True)
    for item in records:
        install_wheel(wheels / item["file"], runtime, packages)
    (runtime / "python314._pth").write_text(
        "python314.zip\n.\nLib/site-packages\n../app\nimport site\n", encoding="utf-8")
    shutil.copy2(launcher, destination / launcher.name)
    app_destination = destination / "app"
    if app_destination.exists():
        shutil.rmtree(app_destination)
    shutil.copytree(ROOT / "app", app_destination,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    for name in ("README.md", "LICENSE", "LICENSE.txt", "CONTRIBUTING.md", "CHANGELOG.md", "RELEASE_NOTES.md", "VALIDATION.md", "WINDOWS_ACCEPTANCE_PROMPT.txt"):
        if (ROOT / name).is_file():
            shutil.copy2(ROOT / name, destination / name)
    rebuild = destination / "build_tools"
    rebuild.mkdir(exist_ok=True)
    for name in ("assemble_windows.py", "launcher.c", "RiverLakeCartography.exe",
                 "runtime-wheels.json", "requirements-runtime.lock.txt", "build_windows.ps1", "build_windows.cmd",
                 "WINDOWS_ACCEPTANCE.md", "windows_build_validation.json", "launcher-build.json", "fetch_font.py", "package_source.py"):
        if (TOOLS / name).is_file():
            shutil.copy2(TOOLS / name, rebuild / name)
    shutil.copy2(ROOT / "requirements-windows.txt", destination / "requirements-windows.txt")
    if (ROOT / "docs").is_dir():
        shutil.copytree(ROOT / "docs", destination / "docs", dirs_exist_ok=True)
    curated_validation = destination / "validation"
    for name in ("english-linux-self-test.json", "english-example-qa.json"):
        if (ROOT / "validation" / name).is_file():
            curated_validation.mkdir(exist_ok=True)
            shutil.copy2(ROOT / "validation" / name, curated_validation / name)
    # Keep all upstream notices with the installed packages and provide an index.
    licenses = destination / "THIRD_PARTY_NOTICES.txt"
    lines = ["RiverLakeCartography third-party software notices", "",
             "Python " + PYTHON_VERSION + ": runtime/LICENSE.txt", "",
             "Package license texts remain in runtime/Lib/site-packages/*.dist-info/",
             "and in package-specific license directories (including native dependencies).", ""]
    for item in records:
        expression = item.get("license_expression") or item.get("license") or "See bundled metadata/license files"
        if len(expression) > 160:
            expression = "See bundled metadata/license files"
        lines.append(f"{item['name']} {item['version']}: {expression}")
    lines.extend(["", "Bundled Noto font: app/resources/fonts/LICENSE-NOTO.txt",
                  "Font copyright and provenance: app/resources/fonts/COPYRIGHT-NOTO.txt and FONT_SOURCE.json",
                  "Bundled map example data: see app/examples source/provenance records.", ""])
    licenses.write_text("\n".join(lines), encoding="utf-8")
    check_cmd = ('@echo off\r\nchcp 65001 >nul\r\ncd /d "%~dp0"\r\n'
                 'start "" /wait "RiverLakeCartography.exe" --self-test --output-dir "%LOCALAPPDATA%\\RiverLakeCartography\\self-test"\r\n'
                 'set "TEST_RESULT=%ERRORLEVEL%"\r\necho.\r\necho Exit code: %TEST_RESULT%\r\n'
                 'echo Report: %LOCALAPPDATA%\\RiverLakeCartography\\self-test\\self_test_report.json\r\n'
                 'pause\r\nexit /b %TEST_RESULT%\r\n')
    (destination / "Check-Application.cmd").write_text(check_cmd, encoding="utf-8")
    manifest = {"app_version": APP_VERSION, "language": "en", "python": PYTHON_VERSION, "python_source": PYTHON_URL,
                "python_archive_sha256": PYTHON_SHA256, "launcher": launcher_info,
                "runtime_packages": records, "native_windows_test": "not performed by assembler",
                "distribution": "portable folder; keep exe, app and runtime together"}
    (destination / "BUILD_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if create_zip:
        archive_path = destination.with_suffix(".zip")
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for file in sorted(destination.rglob("*")):
                if file.is_file() and "__pycache__" not in file.parts:
                    archive.write(file, Path(destination.name) / file.relative_to(destination))
        print(json.dumps({"zip": str(archive_path), "bytes": archive_path.stat().st_size,
                          "sha256": digest(archive_path)}), flush=True)
    print(json.dumps({"distribution": str(destination), "launcher": launcher_info}), flush=True)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "RiverLakeCartography-Windows-x64")
    parser.add_argument("--zip", action="store_true")
    args = parser.parse_args()
    assemble(args.output, args.zip)


if __name__ == "__main__":
    main()
