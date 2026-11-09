# Architecture

## Components

| Location | Responsibility |
|---|---|
| `build_tools/launcher.c` | Native Windows GUI launcher for the private Python runtime |
| `app/main.py` | Local HTTP service, task orchestration, project history, exports and self-test |
| `app/data_service.py` | Place search, bounded retrieval, import validation, geometry preparation and job creation |
| `app/web/` | Local HTML/CSS/JavaScript interface |
| `app/core/render_map.py` | Projected map rendering and output/quality records |
| `app/core/cartographic_labels.py` | Measured area/river labels and layout checks |
| `app/core/check_environment.py` | Dependency, font and projection checks |
| `app/examples/shijiu/` | Reproducible English OSM-derived example |
| `build_tools/assemble_windows.py` | Hash-checked Windows runtime assembly |

## Data flow

The offline example copies prepared data and configuration into a new project. Import validates supplied files and their declared CRS. Online retrieval first resolves a place, then obtains spatial data for the confirmed extent. All three routes produce the same kind of local job, which is passed to the renderer.

The renderer loads and checks geometries, transforms coordinates to a suitable projected CRS, clips the visible area, places required labels and measures layout. It writes completed PNG/SVG only when the applicable checks permit completion. A layout failure can still produce an explicitly identified diagnostic preview and `qa.json`.

Source descriptions are supplied evidence, not certificates issued by the renderer. The program's quality record can establish that a label was placed and a distance check was performed; it cannot establish the legal authority of a boundary or whether every important waterway was retrieved.

## Local service and project boundaries

The service binds to loopback and uses a per-session token and origin checks. Imported configurations are resolved against selected/imported files rather than accepting arbitrary client-provided computer paths. Download routes are bounded to project outputs. Review the integration tests before changing any of these boundaries.

Project data is not uploaded to an LLM by the application. Online lookup necessarily sends a place query or bounding extent to the configured data service. No API key is required for the current public-service defaults, and no credentials should be embedded in a shared project.

## Re-rendering and diagnostics

A re-render produces a new project version and preserves older versions. Status and output hashes identify which files belong to a run. An earlier successful PNG must never be presented as proof that a later failed configuration succeeded.

Explicitly requested names remain required. Automatic candidates may be selected using documented size/length/readability criteria, but a selected candidate that fails layout must remain visible in diagnostics. A user-requested river cannot disappear silently to improve the apparent success rate.

## Portable distribution

Windows receives its own embedded interpreter and Windows wheels. Ordinary end users do not install Python or run a package manager. Development on another operating system uses that system's own environment; successful development tests do not substitute for starting the packaged EXE on Windows.
