# Changelog

## 1.0.0-preview.1 — 2026-11-09

First English public preview of the desktop workbench.

### Included

- Local browser interface backed by a Python service and a native Windows x64 launcher.
- Offline Shijiu Lake example, bounded online place/data retrieval and GeoJSON import.
- Rule-driven river, lake and administrative labels; lower-left legend; projected scale and direction checks.
- PNG/SVG export, source records, quality reports, diagnostic previews and versioned project folders.
- Portable Windows runtime assembly with pinned download hashes.
- English interface, documentation, example labels and community contribution materials.
- Development history, reproducible build guidance and transparent validation records.

### Known limitations

- Difficult river geometry can leave requested labels unplaced; these results are diagnostic previews.
- Public online services can time out or return incomplete administrative/waterway data.
- The original development environment did not establish native Windows execution or actual-browser visual acceptance. See release-specific evidence and `VALIDATION.md`.
- No embedded LLM, monitoring-point positioning, DEM network extraction, dated satellite-water extraction, nationwide mapping or map-approval service.
