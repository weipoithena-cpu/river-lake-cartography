# Validation record

Version: **1.0.0-preview.1**. Baseline observations were recorded on 2026-11-09. This document distinguishes execution, mocked-interface tests and static inspection. New release-specific evidence must identify the tested commit/package and environment.

## Initial implementation baseline

| Check | Observed result |
|---|---|
| Python syntax | Application and renderer modules compiled |
| Data preparation | 10 focused tests passed: coordinate declaration/ranges, complete polygons and holes, administrative levels, requested river names, provenance and portable configuration |
| HTTP and rendering integration | 5 tests passed using actual HTTP requests and actual rendering: session/origin controls, offline example, project download, diagnostic output, version preservation and GeoJSON import |
| Frontend interactions | 11 jsdom tests passed with mocked APIs; extent confirmation, input parameters, diagnostics, re-rendering, downloads and Codex handoff were exercised |
| Original Shijiu Lake example | PNG and SVG generated at 3840 × 2160; 5 river, 8 administrative and 1 lake labels placed; automatic `errors` was empty |
| Font and projection | Actual font rendering passed; a projection round trip had maximum error approximately 1.78 × 10^-15 degrees |
| Windows launcher | A genuine PE32+, AMD64, Windows GUI executable passed header checks |
| Windows dependency inspection | 104 EXE/DLL/PYD binaries were AMD64; no missing third-party DLL name was identified by static inspection |
| Download integrity | The official embedded Windows Python ZIP and 14 pinned Windows wheels were verified against SHA-256 records |

The executed Python baseline used **Linux, Python 3.12.14, NumPy 2.3.5, Matplotlib 3.10.8, Shapely 2.2.0 and pyproj 3.8.0**, with the bundled Noto font. The Windows portable runtime instead uses Python 3.14.10 and its own pinned Windows wheels. Results from one environment are not represented as results from the other.

The original example was rendered before English localization. Translation changes label metrics and therefore requires a new render and layout check. The original counts above remain historical baseline evidence; the English-edition checks are recorded separately below.

Source-age and authority warnings can produce `completed_with_warnings` even with no layout errors. Such a status does not certify the source data. The program keeps manual visual review pending until someone has actually inspected the image.

## Live online trials

1. Photon returned actual search results for Shijiu Lake and Xuanwu Lake.
2. An initial Overpass request returned 39 water polygons, 13 river segments and 15 township polygons near Xuanwu Lake.
3. The trial exposed a China-specific administrative-level mapping issue. The implementation was corrected to map OSM levels 4/5/6 to province/prefecture/county and to request county-level polygons by default. Level 8 is township-level in that setting.
4. Subsequent county requests encountered a 90-second read timeout and a service 5xx response. The errors were reported.
5. Rendering a real retrieved snapshot placed the lake name and one river name, but three suggested river labels failed the along-river layout checks. The output was retained as a diagnostic preview.

These observations establish implemented search/retrieval paths and concrete failure modes. They do not establish that every place query produces a complete, publication-ready map.

## Conditions not established by the original environment

- **Native Windows execution:** not performed in the Linux development environment.
- **Wine execution:** did not complete because the environment denied the required local socket creation. That route was stopped.
- **Real-browser visual acceptance:** not completed because Chromium could not create the required socket. Mocked DOM tests are not a replacement.
- **Geographic authority:** automated rendering does not certify an administrative boundary, survey year, hydrologic relationship or map approval status.

The native acceptance script must run the actual packaged EXE, inspect its generated PNG/SVG and exercise the browser interface on Windows. Record exact results instead of carrying this preview's historical state forward automatically.

## English-edition data verification

English localization preserves every geometry coordinate and OSM object ID in the three example layers. Working-file hashes are refreshed in `app/examples/shijiu/sources.json`; original snapshot hashes remain separate. Names and narrative metadata are translations, and duplicate original-language tags and per-edit usernames are omitted. This is a documented derived dataset, not a byte-identical copy of the source.

The three translated layers were checked with exact coordinate/OSM-ID comparisons and Shapely: 4 administrative polygons, 1 lake polygon and 153 river features; 0 empty geometries and 0 invalid geometries.

The English example was then run through the actual Linux application self-test. It passed with `errors: []`, generated a 3840 × 2160 PNG and an SVG, and placed all **8 administrative, 5 river and 1 lake labels**. Longer English area names are preserved as normal words. River words follow the river orientation with measured text-footprint checks. Dangtu County and Gaochun District use automatic measured interior positions instead of their previous fixed anchors. No feature coordinates were changed to make labels fit.

These results establish the current English example's automated rendering checks on Linux. They do not by themselves establish native Windows or real-browser acceptance. The README image is the actual English render, not a UI mockup or a generated illustration.

### English-edition regression results

All **34 checks passed** after localization: 10 data-preparation checks, 7 typography checks, 5 actual HTTP/render integration checks, and 12 frontend DOM checks using mocked APIs. The executed commands were `python tests/data_service_test.py`, `python tests/test_cartographic_labels.py`, `python tests/test_integration.py`, and `npm run test:ui`, using the configured development dependencies.

The [English Linux self-test record](validation/english-linux-self-test.json) and [example quality record](validation/english-example-qa.json) retain the actual result with portable paths. Source-year warnings remain visible; they were not removed to produce a cleaner status. The [example image](docs/images/shijiu-example.png) is the generated output from that job.

## Evidence locations

- `tests/data_service_test.py`: focused data tests.
- `tests/test_integration.py`: HTTP/render integration tests.
- `tests/test_cartographic_labels.py`: English typography and label-footprint checks.
- `tests/test_frontend_dom.cjs`: mocked frontend DOM tests.
- `tests/live_validation_summary.json`: translated live-trial record.
- `build_tools/windows_build_validation.json`: original static packaging record.
- `build_tools/pe_dependencies.json`: binary dependency inventory.
- `BUILD_MANIFEST.json` in the portable ZIP: runtime identities and assembly checks.

A failure can leave an earlier successful map in its old output folder. Check the current job status, run identifier and output hashes before presenting a file as the latest successful result.
