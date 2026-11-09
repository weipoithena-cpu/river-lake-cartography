# Data preparation and rendering

## Supported input

| Job field | Geometry | Default name property |
|---|---|---|
| `lake_file` | GeoJSON Polygon/MultiPolygon | `name` |
| `rivers_file` | GeoJSON LineString/MultiLineString | `name` |
| `admin_file` | GeoJSON Polygon/MultiPolygon | `name` |

At least one layer is required. An absent or null layer is allowed by the renderer but does not satisfy a user's request for that content. Supplied data must be declared EPSG:4326, longitude first and latitude second. Transform other actual source coordinate systems appropriately before this step; do not relabel offset web-map coordinates as WGS 84.

Validate geometry, names, extent, feature definitions and source records. Preserve original inputs and record conversions/repairs. Invalid geometry and missing required source fields can block rendering. The program does not silently repair administrative boundaries.

## Environment

Use a Python environment with NumPy, Matplotlib, Shapely and pyproj. Requirements are in `../assets/requirements.txt`; the Windows distribution has a separately pinned private runtime. Check actual imports, required font glyphs and a projection round trip. A font file's existence alone is insufficient evidence that it renders the names.

The desktop app uses its bundled Noto font. SVG exports outline text for stable display; they do not preserve editable character text. The original Linux-tested dependency combination is recorded in the repository's `VALIDATION.md` rather than asserted to cover every version satisfying the requirements range.

## Job configuration

Copy `../assets/map_job.template.json` to the project folder and fill actual values. Placeholders and a null extent deliberately make the template incomplete. All relative layer paths resolve from the job file's directory.

| Field | Meaning |
|---|---|
| `schema_version` | Integer 1 |
| `title`, `subtitle` | Actual map content; do not claim absent monitoring sites or flow directions |
| `extent_wgs84` | `[west, south, east, north]` in decimal degrees, without crossing the antimeridian |
| `source_crs` | `EPSG:4326` in this workflow |
| `render_crs` | `auto_utm` or a suitable explicitly identified projected CRS in meters |
| Layer fields | Existing local files, or null for an omitted layer |
| `name_fields` | Per-layer actual property keys |
| `mask_rivers_by_lakes` | Whether river portions overlapping water polygons are hidden; assess whether this fits the data's meaning |
| Label arrays | Required administrative, river and lake labels |
| `source_records` | Evidence for each provided layer under `lake`, `rivers`, `admin` |
| `font_path` | Optional actual font file |
| `output` | Default 3840 × 2160, 240 dpi; this implementation requires 16:9 |

Each source record requires `source_name`, `source_url`, `year`, `license` and `authority_status`. Use “not specified” where the survey/data year is unknown; a retrieval year is not a substitute. A verifiable institutional file reference may be used where there is no public URL. Never invent one. Optional fields include attribution, retrieval date, notes, version and metadata URL. OSM-derived outputs need [contributor attribution and license access](https://www.openstreetmap.org/copyright).

Automatic UTM selection is limited to a local extent in a suitable latitude band, within one zone, without crossing the equator and with geographic spans no more than 6 degrees. The renderer also rejects very broad extents even when a projection is manually supplied. The desktop online-retrieval route imposes tighter bounds. Do not bypass these gates to force a national map into a local template.

Supported output dimensions are 1280–7680 pixels wide, 720–4320 high, 72–600 dpi, with 16:9 aspect. Changing dpi changes the relationship between points and pixels and can change layout.

## Label definitions

Administrative labels:

```json
{"name":"Example County","level":"county","position":null}
```

Levels are `province`, `city` and `county`. A null position asks the program to find an internal location. A supplied `[longitude, latitude]` must be valid; it is not silently moved when invalid. An upper-level label can specify actual supplied `members`, for example two districts, only with verified affiliation. All such labels denote areas, not government seats.

River labels:

```json
{"source_name":"Example River","display_name":"Example River","anchor_near":null,"side":1}
```

The source name must match real input geometry. A different display name requires a documented `name_basis`. An `anchor_near` coordinate guides label placement, not geometry displacement. `side` selects an offset side; size, spacing and offset may be configured within readable limits. A missing, fully masked, too-short or collision-prone river yields a reported placement failure rather than a fabricated label.

Lake labels:

```json
{"name":"Example Lake","position":null,"font_size_pt":20}
```

List the principal lake explicitly so it cannot disappear as an optional automatic suggestion. An empty list is appropriate only when omitting that labeling is an actual documented choice, not a way to evade a required-name check.

## Run and inspect

From the repository root:

```sh
python app/core/render_map.py --job path/to/map_job.json --output-dir path/to/output
```

A successful run returns zero and writes `map.png`, `map.svg` and `qa.json`. A layout failure can write `diagnostic_preview.png/svg` plus issues and return nonzero; an invalid input may write only the quality report. Inspect status and hashes before opening a file. Earlier successful maps can remain in an existing directory and do not establish that the current run succeeded.

Read the quality report, inspect the actual image and check readability at its final presentation size. Source authority and real geographic correspondence remain distinct from measured layout checks. See `quality-gates.md`.

## Scope

This module handles prepared local vector data, projected rendering, along-river text, area-label containment, fixed legend placement, scale/direction information and reproducible outputs. It does not itself perform DEM drainage extraction, satellite segmentation, monitoring-site positioning, screenshot registration, hydrodynamic modeling or administrative map-approval submission.
