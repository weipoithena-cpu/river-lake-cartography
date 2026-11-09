# How the workbench was made

This document records the project's design and implementation process so contributors can reproduce and improve it. It summarizes engineering decisions and evidence without publishing private conversation transcripts or machine-specific personal paths.

## 1. Start with a concrete mapping problem

The original task was to prepare a presentation map of Shijiu Lake, surrounding administrative areas, principal connected rivers and, eventually, monitoring locations. The intended operator was a water-environment planning professional who did not use GIS software. Initially there were no supplied spatial datasets.

That requirement made data acquisition, provenance and repeatability as important as drawing. A plausible-looking image was insufficient: the tool needed actual geometry, identified sources, known coordinates, reproducible output and a visible way to report missing information.

Monitoring-location processing was explicitly deferred. Two future input routes were discussed—coordinates and an approximate location diagram—but neither was declared implemented. The present tool must not invent monitoring sites or imply that the built-in example contains them.

## 2. Turn cartographic expectations into explicit rules

Three requirements were fixed before building the interface:

1. River names must follow the actual river path, without leader lines.
2. The legend must remain inside the lower-left corner of the main map frame.
3. Province, city and county/district names must use verified hierarchy and lie inside the corresponding visible area, considering the complete text footprint.

The source research distinguished law, technical references and project style. Standard-map portals were examined for usable source material; map-management and geographical-name documents were consulted for their applicable content. Some sources were retrieved in full, while other services were unavailable or known only through indexed text. Those evidence limits were recorded rather than described as complete mastery of a website.

An initial reusable `river-lake-cartography` skill organized the workflow into instructions, references, a job template, an environment checker, a renderer and label-placement helpers. The desktop application reuses the same rendering approach. Relevant English reference material is now in `app/core/references`.

## 3. Establish a working Python environment

The initial Windows environment had NumPy and Matplotlib but lacked Shapely and pyproj. A project-specific virtual environment was then configured, installing compatible wheels and verifying dependency consistency, actual font rendering and a coordinate-system round trip.

That validation established a local development environment; it was not yet a distributable application. The portable workbench later received its own independent embedded Windows Python runtime and a pinned wheel inventory. These two environments must not be conflated in test reports.

The implementation uses NumPy, Matplotlib, Shapely and pyproj. Shapely supplies geometry operations, pyproj performs actual coordinate transforms, and Matplotlib renders measured labels and map elements. Geographic coordinates are never made projected merely by changing a CRS label.

## 4. Define a reproducible job format

A map job records the extent, source and rendering CRS, layer paths, name fields, required labels, source records, font and output dimensions. The renderer accepts local EPSG:4326 GeoJSON and produces PNG/SVG plus a machine-readable quality record.

The distinction between a source name and a display label matters. A renamed or translated label still needs a documented relationship to the source feature. Higher-level administrative labels can use unions of supplied member areas only when affiliation is known; a partial union is not a complete provincial or municipal boundary.

Output is currently 16:9. The default 3840 × 2160 size is a presentation-export choice, not a spatial-accuracy claim. SVG text is outlined for stable display, so it should not be advertised as directly editable character text.

## 5. Build the desktop workflow

The application is a Python local HTTP service with a browser interface. A small native Windows launcher starts the bundled interpreter, passes command-line arguments, opens the local app and reports startup errors. The service listens on loopback; imported files are processed on that computer.

Three entry routes feed the same project pipeline:

| Route | Reason for including it |
|---|---|
| Offline Shijiu Lake example | Gives recipients a reproducible first task without a network dependency |
| Local GeoJSON import | Lets users work with verified institutional or otherwise prepared data |
| Photon/Overpass lookup | Gives users without initial data a bounded-area starting point |

The service writes isolated project folders, reports progress, and distinguishes successful output from diagnostics. Re-rendering produces a new version instead of overwriting a previous accepted result. A project ZIP keeps the data and configuration portable.

The Codex handoff feature produces a prompt containing the actual project paths and the unresolved task. It does not embed an LLM, silently transmit imported data to a model or promise autonomous data verification.

## 6. Test real data and retain inconvenient results

The Shijiu example uses authentic OSM-derived geometry. Initial rendering placed the five requested river names, eight administrative names and one lake name. Source records preserve limitations: the lake survey year is unknown; administrative polygons are collaborative data; and the full river-network query/time cannot be reconstructed completely from the available provenance files.

A second-lake trial used actual Photon and Overpass responses near Xuanwu Lake. It exposed a China-specific administrative-level error: OSM level 8 refers to township-level units there. The implementation was corrected to use the appropriate province/prefecture/county mapping and default county retrieval.

Later service calls encountered timeouts and a server error. A render from a real cached snapshot also failed to place three automatically selected river labels. These are recorded as failures or diagnostic results. They are not erased because another example rendered successfully.

The automated tests cover geometry preparation, source declarations, HTTP session/origin protection, imported paths, real rendering, preservation of prior versions, and frontend interaction with mocked APIs. Test type is always identified: a simulated DOM result is not an actual-browser screenshot review.

## 7. Assemble a portable Windows package

The build process downloads an official embedded Windows Python archive and pinned Windows wheels, verifies their hashes and assembles a private runtime. A genuine AMD64 Windows GUI launcher is included with its C source. The distribution keeps the EXE, application and runtime adjacent.

This is a portable folder packaged as a ZIP. The EXE is a launcher, not a self-sufficient executable that can be detached from the other files. Reproducible source and build scripts are provided so collaborators can audit and rebuild it.

Static checks inspected Windows PE architecture and imported DLL names. Actual Python rendering and HTTP integration were exercised on Linux. Wine and Chromium could not create required sockets in the original environment; those attempts stopped. Native Windows execution and real-browser acceptance therefore remained explicit follow-up requirements, rather than being inferred from static checks.

## 8. Prepare the English public edition

The public edition translates the interface, documentation, messages, examples and contribution material. Example feature geometries and OSM IDs remain unchanged, while descriptive fields and map labels become English. Source records distinguish original hashes from translated working-file hashes and identify the derived data license.

Original Chinese government PDFs are not redistributed in this edition. The reference index keeps official URLs and historical read-status information, with English operational summaries. The summaries do not replace the official documents or turn project-specific design choices into national requirements.

English labels can be longer than the original labels. Localization therefore requires new render/layout checks; a successful earlier-language map is not sufficient evidence for the English version. This release remains a preview while those results and native-platform evidence are recorded explicitly.

## 9. Continue through focused community contributions

The next work should improve concrete limitations without weakening the rules: reliable native acceptance, better along-river English labels, clearer partial-data handling and robust provider fallback. Monitoring-location inputs, DEM extraction and dated water-surface products require separate designs and validation before integration.

The source, configuration, examples, test scripts and build instructions are intended to make improvements reviewable. For a change, explain the problem, show the resulting behavior, retain provenance and record the actual test environment. See [CONTRIBUTING.md](../CONTRIBUTING.md) and [ROADMAP.md](ROADMAP.md).
