# River Lake Cartography v1.0.0-preview.1

First English public preview of a portable desktop workbench for river, lake and administrative-area presentation maps.

## Download and run

Download **RiverLakeCartography-Windows-x64.zip**, extract the entire archive and open `RiverLakeCartography.exe`. Keep the EXE, `app` and `runtime` folders together. The package targets Windows 10/11 x64 and includes its own Python runtime, libraries and font; recipients do not need Python, Codex or GIS software installed.

Start with the offline Shijiu Lake example. Use the application's exit button when finished. `RiverLakeCartography-Source.zip` supplies source and build material; `SHA256SUMS.txt` identifies the attached ZIP files.

## Included in this preview

- English local browser interface, offline example, bounded Photon/Overpass lookup and GeoJSON import.
- Rule-driven river names along river geometry without leader lines, a lower-left legend and hierarchical administrative labels inside their visible areas.
- PNG/SVG export, reproducible project configuration, source records, quality reports, diagnostic previews and version history.
- Complete development history, cartographic references, tests and reproducible Windows packaging scripts.

## Verification

The English implementation passed **34 regression checks**: 10 data, 7 typography, 5 actual HTTP/render integration and 12 mocked frontend DOM checks. Its actual Linux self-test generated a 3840 × 2160 example with all 8 administrative, 5 river and 1 lake labels placed and no automatic errors. Source-age warnings remain recorded.

The supplied preparation environment did **not** execute the native Windows program or complete a real-browser visual acceptance. If this release was published by the supplied GitHub Actions workflow, its successful Windows job additionally records an actual EXE self-test for that newly built package. Consult that run and package manifest for the evidence; automated Windows execution still does not establish desktop-browser visual acceptance.

## Known limits

Difficult river geometry can prevent label placement; such outputs remain diagnostic previews. Public services can time out or return incomplete data. Open administrative boundaries are not certified boundaries, and automated layout does not provide a map approval number.

This release does not embed an LLM or implement monitoring-point positioning, screenshot registration, DEM drainage extraction, dated satellite-water extraction or nationwide mapping. SVG text is outlined rather than editable character text.

Application code is MIT-licensed. Dependencies and the Noto font retain their licenses. The authentic OSM-derived example is licensed under ODbL 1.0 with attribution to OpenStreetMap contributors. English names are documented working translations/transliterations.

Please report reproducible problems through Issues and contribute focused improvements through pull requests. See `CONTRIBUTING.md`, `VALIDATION.md` and the roadmap in the repository.
