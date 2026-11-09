# Reusable mapping prompt

Replace the bracketed fields with the actual project requirements. Omit unavailable content instead of inventing it. This prompt can guide a separate AI-assisted preparation/review session; it is not a feature that makes the desktop application a built-in LLM.

```text
Prepare a reproducible river/lake and administrative-area map using River Lake Cartography.

Project:
- Map title: [TITLE]
- Main lake/river and geographic area: [AREA]
- Final use and displayed size: [PRESENTATION OR REPORT; EXPECTED SIZE]
- Required administrative levels: [PROVINCE / CITY / COUNTY]
- Required river/lake names: [NAMES, OR STATE THAT THEY NEED SOURCE VERIFICATION]
- Supplied files and known CRS: [FILES; ACTUAL CRS; OR NO FILES AVAILABLE]
- Data reference date: [DATE OR NOT SPECIFIED]
- Output folder: [FOLDER]
- Requested outputs: [PNG, SVG, REPRODUCIBLE PROJECT ZIP]

First inspect the available data, its provenance, license, coordinate definition,
and coverage. Use traceable source geometry. Distinguish lake outline, observed
water surface, management boundary, watershed and administrative boundary.
Do not infer flow direction or monitoring locations without evidence.

Apply these project rules:
1. River names follow the actual river path; no river-name leader lines.
2. Legend inside the lower-left of the main map frame.
3. Province/city/county names use confirmed hierarchy and consistent styling;
   the full text footprint stays inside the correct visible jurisdiction.
4. Do not move real features or silently omit requested labels to fit the page.

Prepare GeoJSON and map_job.json, record transformations and source limitations,
and run the renderer. Read qa.json and inspect the actual output at full size
and at the intended presentation size. If a label cannot be placed, retain a
clearly identified diagnostic preview, explain the cause and adjust only
legitimate layout/data choices. Record unperformed checks as unperformed.

Deliver the actual map, configuration, source record and relevant quality
results. Explain material omissions and unresolved limitations. Do not claim
that automated layout certifies boundaries or supplies map approval.

Monitoring-point positioning is outside this task unless I provide a separate,
explicitly agreed workflow and suitable inputs.
```
