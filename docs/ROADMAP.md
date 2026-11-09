# Roadmap

This is a list of proposed improvements, not a promise that the current release implements them.

## Highest priority

| Work | Completion evidence |
|---|---|
| Native Windows and browser acceptance | Actual packaged EXE starts, offline example renders, imports/exports work, exit behavior is verified and the interface is visually inspected |
| English river-label placement | Difficult real examples place complete readable names along their correct river paths; required labels never disappear silently |
| Online reliability | Clear retry/partial-data behavior, retained provenance, bounded requests and actionable service errors |
| Administrative-area consistency | Tests cover supported country-specific level mappings, parent relationships, clipped polygons and full-label containment |
| Reproducible release evidence | A package is tied to its source commit, dependency hashes and actual test results |

## Data and workflow improvements

- Add documented adapters for GeoPackage and Shapefile with explicit CRS handling.
- Improve user control over which river and administrative names are required.
- Offer useful layout suggestions when a diagnostic preview cannot place a label.
- Make source age, geometry definitions and completeness more visible before rendering.
- Support institutional data providers through explicit, licensed adapters.

## Separate future modules

Monitoring-point coordinates and diagram-based approximate positioning require a dedicated workflow, uncertainty model and verification. DEM drainage extraction needs suitable elevation data and hydrologic preprocessing. Satellite water mapping needs a specified observation date, sensor, cloud/quality treatment and validation. None of these can be claimed merely because a GeoJSON map renders.

An optional LLM-assisted preparation layer may help users describe tasks or review diagnostics. It should have explicit data-transfer controls, reproducible generated configuration and no authority to silently fabricate geometry or mark unchecked maps approved.
