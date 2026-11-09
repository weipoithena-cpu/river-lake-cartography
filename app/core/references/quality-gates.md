# Quality gates and failure handling

Acceptance concerns the actual map and its inputs. A structurally valid application or configuration does not automatically establish geographic correctness, visual acceptance or legal approval.

## Separate three kinds of review

| Review | Can establish | Cannot replace |
|---|---|---|
| Automated checks | Input structure, coordinate range, placed labels, bounding boxes, collisions, lower-left legend, scale checks and image size | Source authority, real hydrologic relationships, source freshness or final visual judgment |
| Visual/source review | Correct label-feature association, clear emphasis, unobscured details, presentation readability and source/feature consistency | A competent authority's map review |
| Applicable public-use/administrative review | Requirements for a particular final product and use | Not established by a renderer's `completed` status |

Record passed, failed, not checked or not applicable, with evidence. Without a point layer, say no points are included; do not report point accuracy as passed.

## Before rendering

Confirm the map title, subject, scope and intended use. Require actual needed layers, name fields, geometry types and CRS definitions. Distinguish data year, retrieval date and publication version. Check administrative hierarchy and partial-member coverage. Establish the principal-river list where required, and omit unsupported flow arrows. Record sources, licenses and original-map approval information without borrowing authority for a derived map.

## Read the current `qa.json`

Read `status`, `errors`, `warnings`, `outputs`, the run ID and hashes. A nonzero result or `failed` requires correction. `completed_with_warnings` still needs judgment about whether each warning affects the task.

| Record | Check |
|---|---|
| `layers` | Actual layers, accepted/empty/invalid geometries, visible counts, sources, hashes and river masking |
| `crs` | Actual source/render CRS, selection method and extent |
| `requested_labels` / `label_counts` | Agreement with the required names and explicit principal-lake label |
| `admin_labels` / `lake_labels` | Feature correspondence, location, full text containment and failure reasons |
| `river_labels` | Selected geometry, text order/orientation, offset, placement and zero leader lines |
| `missing_or_unplaced_labels` | Every missing name explained and resolved according to task importance |
| `layout_checks` | Legend containment/location, text boundaries/collisions, administrative containment and scale |
| `font` | Actual font identity/hash and missing glyphs |
| `image_size_px_measured` / `outputs` | Actual image dimensions, current files and hashes |
| `prior_success_files_not_updated` | Earlier successful files that are not evidence of success for this run |

Layout-canvas coordinates are not necessarily final PNG pixel coordinates. Algorithm thresholds are implementation checks, not statutory spatial-accuracy standards.

## Inspect the image

- View the whole map for extent, emphasis, proportions, hierarchy, title, legend and scale/direction readability.
- Inspect every river name for correct feature association, complete sequence, along-line placement, appropriate orientation and unobscured mouths.
- Inspect each administrative label's entire footprint within the corresponding visible polygon and confirm it is an area name rather than an implied government seat.
- Inspect water boundaries, islands, mouths, confluences and overlapping administrative lines for accidental masking.
- Match every legend entry to the map; inspect required source/attribution text and possible geographic obstruction.
- Zoom in for detail, then reduce to the actual presentation size. High pixel counts do not repair tiny text. Compare SVG and PNG where both are delivered.

Record the inspected file and hash, date, whether the actual image was opened, findings and unresolved issues. Do not mark manual visual acceptance passed without looking at the image.

## Completion blockers and correction

Correct materially wrong coordinates/geography, omitted required labels, reversed text, leader lines, incorrect administrative containment, misplaced legend, obscured key features, unreadability, false scale or source/approval misuse before calling the map complete.

Correct data first, then extent and layout. Do not move geography or suppress required labels/errors. Re-run the checks relevant to the issue and the necessary whole-image inspection. A diagnostic preview is useful for iteration but must remain identified as unaccepted.

Save the successful image with its job, provenance and check record. A new title, style, extent or data version requires a new run and appropriate review; earlier acceptance is not inherited automatically.
