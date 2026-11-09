# Cartographic rules for river, lake and administrative-area maps

Reference record date: 2026-11-09. Read these rules before preparing a job. A requirement below is an execution rule for this project unless it explicitly identifies an applicable legal provision. The entire visual style is not represented as a uniform national specification.

## 1. Authority and scope

| Basis | Use in this project |
|---|---|
| Applicable map and geographical-name regulations | Check actual scope, standard names, administrative boundaries, public-use requirements and approval-number handling |
| Cartographic technical references | Apply line names along lines, area names inside areas, point names beside actual points, and consistent symbols/legend |
| Standards catalogs | Establish a standard's identity and intended scale; obtain the complete standard before claiming compliance with its symbol tables |
| Adopted project rules | No river-name leader lines; legend inside the lower-left frame; hierarchical administrative names contained in their actual visible areas |
| Default presentation style | Light land, blue water, white background, 16:9, PNG/SVG; adjustable design choices rather than mandated legal colors or sizes |

Technical sources include the [Second National Geographical Names Census Working Procedures](https://www.abazhou.gov.cn/abazhou/c109727/201501/943e47fc205a4b09bd805356af5f83c1.shtml), particularly the labeling provisions; the [Provincial Spatial Planning Preparation Guide, Appendix H](https://dnr.gxzf.gov.cn/ztzl/gtkjgh/jsbz/gjjsbz/P020231211346162654422.pdf); and the catalogs for [GB/T 24354-2023](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=ACE4299ACBA71AB50AFED1462C19A75B) and [GB/T 20257.3-2017](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=288C537E66D4001BD11CBCEFF0FBE3C5). Read-status limitations are in `knowledge-sources.json`. Catalog access does not establish that every symbol table was read.

## 2. Geographic content and spatial relationships

1. Every position, outline, name, affiliation and important relationship needs a data basis. Do not move waterways, shores or administrative boundaries to improve composition, and do not invent precise geography with generative images.
2. Record the source CRS, date, provider and feature definition. An observed water surface, conventional lake outline, management limit, watershed and administrative boundary are different objects.
3. Apparent alignment with a background does not prove a CRS. Transform from the actual source definition and retain provenance; do not merely change a coordinate-system label.
4. Clipping, joining or simplifying rivers must not invent connections, move mouths, cross divides or merge distinct rivers with the same name. Record any geometry repair and its effect.
5. Open collaborative data can support a documented working map. A neat render does not turn it into an officially certified boundary or evidence for physical demarcation.
6. Establish the principal-river list from suitable sources. Five available named rivers do not establish that only five important rivers exist.
7. Inflow, outflow, diversion and backflow may depend on water level and operation. Draw direction arrows only when supported. Text reading direction does not represent water-flow direction.

## 3. Rivers and lakes

### River labels

- Bind each label to the appropriate actual visible river geometry and an evidenced name. Handle differently named sections separately and document aliases/translations.
- Arrange a complete readable name along a sufficiently long, reasonably smooth section. Maintain correct reading order without reversed text or abrupt orientation changes.
- Maintain consistent modest offset from the river. Do not distribute one name across adjacent rivers, force it through a tight bend or mouth, or let a line obscure the letters.
- **Do not use river-name leader lines, callout arrows or an off-map name list as a replacement for along-river labels.** If there is no suitable segment, adjust the label location, readable size or map extent. If it still fails, retain an explicit diagnostic item.
- Repeated labels are appropriate only where needed on a long river; they must not imply different rivers.

### Lake labels

Place a lake name inside its actual water polygon in a stable readable area. Avoid islands, narrow bays and unrelated water bodies. Adjust type size to the lake and map, retaining the shoreline's recognizability. Do not assign a principal lake name to a different clipped polygon merely because it is the largest visible area.

## 4. Administrative names and government seats

| Object | Required meaning and treatment |
|---|---|
| Province, city, county/district area | An area label inside its correct visible polygon; test the whole text footprint rather than just its center |
| Capital or government seat | A verified point and appropriate point symbol with associated text; never an arbitrary area centroid |
| Administrative boundary | A level-specific line consistent with the legend; water fill must not accidentally conceal it |

Use verified names and parent relationships. A name ending in a word equivalent to “city” does not by itself establish prefecture/county rank. Keep same-level typography consistent; hierarchy may use different style without claiming a nationally mandatory point size.

Area labels should normally remain upright and clearly associated with their polygon. Recheck containment after clipping. An upper-level visible area may be assembled from supplied lower-level members only where their affiliation is known and recorded. A partial member union is not a complete provincial or city boundary.

The bundled renderer generates area names, not government-seat points. A county-seat symbol in an external map does not establish that county boundaries are available in that map.

## 5. Legend, symbols and marginal information

1. **Fix the legend inside the lower-left corner of the main map frame.** This is the adopted project rule. The planning guide's lower-left/lower-right options do not mean all maps nationally must use the lower-left.
2. Reserve legend space before label placement. Avoid obscuring the main lake, critical mouths or administrative relationships. Adjust extent or whitespace, not real geography.
3. Include only present symbols that need explanation. Legend colors, widths, dashes and marker sizes must match the map. Do not include monitoring points, flow arrows or boundaries absent from the data.
4. Distinguish administrative, watershed and management boundaries when present. Color intensity must not imply an undefined water-quality class.
5. Keep legend, scale bar, north indicator, source text and geographic labels mutually readable.
6. Record map source, thematic source and original approval number separately. An original map's number is not proof that a derived map is approved.

## 6. Scale, direction and export

Use a suitable local projection and equal scaling of its axes. A scale bar must derive from checked distances, not a plausible manually typed distance. Graphical scales remain useful when a presentation image is resized; a numeric representative fraction depends on the final physical size.

The renderer records projected/geodesic scale checks. A wide extent, unsuitable projection or excessive error needs a suitable mapping approach rather than bypassed checks. A north indicator must follow the actual map orientation, accounting for the distinction between grid north and true north where relevant.

Choose pixels and type for the final reading size. The default 3840 × 2160 pixels is not a geographic accuracy guarantee. Verify all required glyphs. SVG outlines improve font portability but are not editable character text.

## 7. Conflict resolution and acceptance

Resolve conflicts in this order: verify data, select another suitable line/area position, adjust readable type/spacing, revise the extent/whitespace, and consider a separately designed inset if necessary. A required feature must not disappear silently.

Wrong CRS or geography, river-name leader lines, misplaced administrative names, a displaced legend, omitted required names, false scale or approval-number misuse block completion. Quantify what the program can check and inspect the actual image for the rest. An unchecked item cannot be recorded as passed.

Monitoring-location positioning is outside the current workflow. Complete the available river/lake/administrative map without adding random points or apparently precise invented coordinates.
