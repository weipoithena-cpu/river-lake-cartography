"""Check the local renderer's Python packages, projection data, and multilingual font.

Run with the same Python interpreter that will run render_map.py.
This script does not install packages or change the computer.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import platform
import sys


def select_font(font_path: str | Path | None = None) -> Path:
    from matplotlib.font_manager import FontProperties, findfont
    from matplotlib.ft2font import FT2Font

    if font_path:
        candidates = [Path(font_path).expanduser()]
    else:
        windows_fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        candidates = [
            windows_fonts / "msyh.ttc", windows_fonts / "simhei.ttf",
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
            Path("/System/Library/Fonts/PingFang.ttc"),
            Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
        ]
        for name in ("Microsoft YaHei", "Noto Sans CJK SC", "PingFang SC", "SimHei"):
            try:
                candidates.append(Path(findfont(FontProperties(family=name),
                                                fallback_to_default=False)))
            except ValueError:
                continue
    failures = []
    for candidate in candidates:
        if not candidate.is_file():
            failures.append(str(candidate) + ": file missing")
            continue
        try:
            font = FT2Font(str(candidate))
            missing = [c for c in "\u6cb3\u6e56\u7701\u5e02\u53bf\u533a\u5730\u56fe" if font.get_char_index(ord(c)) == 0]
            if missing:
                failures.append(str(candidate) + ": missing " + "".join(missing))
                continue
            return candidate.resolve()
        except Exception as exc:
            failures.append(str(candidate) + ": " + str(exc))
    raise RuntimeError("No suitable multilingual font found. Install Noto Sans CJK or specify font_path. "
                       + "; ".join(failures[:5]))


def collect_environment(font_path: str | Path | None = None) -> dict:
    result = {
        "python": sys.version.split()[0], "executable": sys.executable,
        "platform": platform.platform(), "packages": {}, "errors": [],
    }
    if sys.version_info < (3, 10):
        result["errors"].append("Python 3.10 or later is required.")
    modules = {}
    for name in ("numpy", "matplotlib", "shapely", "pyproj"):
        try:
            module = importlib.import_module(name)
            modules[name] = module
            result["packages"][name] = getattr(module, "__version__", "unknown")
        except Exception as exc:
            result["errors"].append(f"{name}: {type(exc).__name__}: {exc}")
    if "pyproj" in modules:
        try:
            project = modules["pyproj"].Transformer.from_crs(
                "EPSG:4326", "EPSG:32633", always_xy=True)
            inverse = modules["pyproj"].Transformer.from_crs(
                "EPSG:32633", "EPSG:4326", always_xy=True)
            x, y = project.transform(15.0, 45.0)
            lon, lat = inverse.transform(x, y)
            error = max(abs(lon - 15.0), abs(lat - 45.0))
            result["projection_roundtrip_error_degrees"] = float(error)
            if not error < 1e-7:
                result["errors"].append("The projection round-trip check failed.")
        except Exception as exc:
            result["errors"].append("The projection database is unavailable: " + str(exc))
    if "matplotlib" in modules:
        try:
            selected = select_font(font_path)
            result["font_path"] = str(selected)
            modules["matplotlib"].use("Agg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            from matplotlib.font_manager import FontProperties
            figure = Figure(figsize=(2, 1), dpi=80)
            canvas = FigureCanvasAgg(figure)
            figure.text(.1, .5, "River and Lake Map", fontproperties=FontProperties(fname=str(selected)))
            canvas.draw()
            result["font_render_buffer_shape"] = list(canvas.buffer_rgba().shape)
        except Exception as exc:
            result["errors"].append("Font/rendering check failed: " + str(exc))
    result["status"] = "ready" if not result["errors"] else "not_ready"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-path", type=Path)
    args = parser.parse_args()
    result = collect_environment(args.font_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
