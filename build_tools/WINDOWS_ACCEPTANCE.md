# Native Windows acceptance

The portable package contains a real Windows x64 launcher, an embedded Python 3.14.10 interpreter and Windows dependency wheels. Recipients do not need to install Python, a GIS application or Codex.

The original preparation host was Linux. PE format, architecture and imported DLL names can be checked there; native execution evidence must be produced on Windows. The GitHub Actions workflow runs the actual launcher self-test on a Windows runner. Read its results before describing that build as tested on Windows. Browser visual acceptance remains a separate check.

## Check an extracted download

1. Extract the complete ZIP into an accessible directory.
2. Keep `RiverLakeCartography.exe`, `app` and `runtime` together.
3. Double-click `Check-Application.cmd`.
4. Require an exit code of `0`, report `status: passed` and an empty `errors` list.
5. Read `%LOCALAPPDATA%\RiverLakeCartography\self-test\self_test_report.json`.
6. Double-click `RiverLakeCartography.exe` and inspect the English interface, example preview and PNG/SVG exports.

The full instruction for a local Codex acceptance run is in `WINDOWS_ACCEPTANCE_PROMPT.txt`. It requires recording actual executable paths, runtime versions, output images and QA results, while keeping unperformed checks explicit.

## Rebuild on Windows

Use a build computer with Python 3.10 or newer and run:

```powershell
.\build_tools\build_windows.ps1
```

The script creates an isolated build environment, downloads and verifies pinned runtime files, synchronizes the application source, runs the actual EXE self-test and creates the portable ZIP only after the self-test report and exit code pass. Build records are copied into the distribution's `validation/windows` directory.

A different build-time Python path can be supplied with `-PythonPath`. A different output folder can be supplied with `-OutputDirectory`. Build-time Python and the application's embedded Python are separate interpreters.

## Recompile the launcher

`launcher.c` is the source for the precompiled `build_tools/RiverLakeCartography.exe`. Its SHA-256 is recorded in `launcher-build.json`; the assembler rejects source or binary changes that no longer match this record. Recompile with a compatible Zig toolchain:

```text
zig cc -target x86_64-windows-gnu -municode -O2 -Wl,--subsystem,windows launcher.c -o RiverLakeCartography.exe -luser32
```

Update the source and binary hashes in `launcher-build.json` after recompiling. Ordinary application changes only require reassembly.

## Cross-host assembly

```text
python build_tools/assemble_windows.py --zip
```

This assembles Windows artifacts on any supported build host. It does not execute the Windows runtime and therefore leaves `native_windows_test` as not performed. It is not a PyInstaller cross-compilation.

## Upstream documentation

- [Python on Windows: the embeddable package](https://docs.python.org/3/using/windows.html#the-embeddable-package)
- [GitHub Actions checkout](https://github.com/actions/checkout)
- [GitHub Actions Python setup](https://github.com/actions/setup-python)
- [GitHub Actions artifact upload](https://github.com/actions/upload-artifact)
