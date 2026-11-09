"""Fetch the exact upstream Noto font used for reproducible label measurements.

Existing matching files require no network access. An existing different file
is never replaced silently. The portable package already includes this font;
this helper is for source checkouts and build hosts.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
FONT_URL = "https://raw.githubusercontent.com/notofonts/noto-cjk/523d033d6cb47f4a80c58a35753646f5c3608a78/Sans/OTC/NotoSansCJK-Regular.ttc"
FONT_SHA256 = "b76b0433203017ca80401b2ee0dd69350349871c4b19d504c34dbdd80541690a"
FONT_BYTES = 19484784
FONT_PATH = ROOT / "app" / "resources" / "fonts" / "NotoSansCJK-Regular.ttc"
LICENSE_PATH = FONT_PATH.with_name("LICENSE-NOTO.txt")
LICENSE_SHA256 = "6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2"


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def fetch_font(destination: Path = FONT_PATH) -> dict:
    if not LICENSE_PATH.is_file() or digest(LICENSE_PATH) != LICENSE_SHA256:
        raise RuntimeError("The exact upstream font license must be present before distributing the font")
    if destination.is_file():
        if destination.stat().st_size != FONT_BYTES or digest(destination) != FONT_SHA256:
            raise RuntimeError("Existing font differs from the pinned source; preserve it and resolve the mismatch before rebuilding")
        return {"status": "verified_existing", "file": str(destination), "sha256": FONT_SHA256}
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".download")
    request = urllib.request.Request(FONT_URL, headers={"User-Agent": "RiverLakeCartography-build/1.0"})
    try:
        count = 0
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > FONT_BYTES:
                    raise RuntimeError("Downloaded font is larger than the pinned file")
                output.write(block)
        if count != FONT_BYTES or digest(temporary) != FONT_SHA256:
            raise RuntimeError("Downloaded font failed the size or SHA-256 check")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {"status": "downloaded_and_verified", "file": str(destination), "sha256": FONT_SHA256}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=FONT_PATH)
    args = parser.parse_args()
    print(json.dumps(fetch_font(args.output)))


if __name__ == "__main__":
    main()
