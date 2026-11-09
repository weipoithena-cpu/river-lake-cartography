# Standard-map services: discovery, retrieval and verification

Historical check date: 2026-11-09. Recheck actual resources for each project. Separate search-index evidence, live-page access, downloaded files and visual inspection. Record only the work actually performed.

## Service entry points and observed access

| Source | Recorded observation | Limit |
|---|---|---|
| [User-specified national entry](http://bzdt.ch.mnr.gov.cn/index.html) | Direct page/browser/ordinary HTTP access failed in the original session | A session failure is not evidence of permanent closure |
| [Tianditu standard-map service](https://bzdt.tianditu.gov.cn/) | Search-index text was available; direct access failed | No verified migration, registration, editing or export trial |
| [Jiangsu official catalog](https://zrzy.jiangsu.gov.cn/jsbzdt/index.html) | Ordinary HTTP returned 200 and the catalog HTML was read | Specific downloaded samples were checked; do not assume every file/edition is identical |
| [Anhui official entry](https://zrzyt.ah.gov.cn/ztlm/ahsbzdtfw/index.html) | Returned 403; the catalog was not read | Do not infer attachment formats or assert the cause of the response |

The indexed national service supports name/approval-number search and categories such as China, world, thematic, reference and self-service maps. Use the current visible page and actual result links, not remembered card positions or guessed file numbers. Descriptions of JPG/EPS or self-service output do not establish the format of every individual download.

A [China Geological Survey announcement](https://www.cgs.gov.cn/ywdt/ddyw/202209/t20220909_819612.html) explains reference-map provision. A [Chinese Society for Geodesy, Photogrammetry and Cartography directory](https://www.csgpc.org/list/254.html) can help locate provincial services; any directory can lag current links.

## Retrieval procedure

1. Define area, theme, intended use, required administrative detail, extent and reference date.
2. Compare specific official map sheets by scale, content, neighboring areas, language and edition.
3. Follow observed preview/download links and record both page and file URLs.
4. Retain original files and record byte size and SHA-256.
5. List archive members and actual extensions before extracting needed files; verify file type.
6. Inspect the complete image, then the title, legend, scale, approval number and attribution.
7. Record observed metadata and choose unchanged-background use, graphical editing or a separately sourced GIS-data workflow.
8. Inspect readability at the final presentation size and retain source/change/review records.

Record unknown values as unknown. Keep publication edition, survey/data date, catalog update, HTTP Last-Modified and retrieval date separate. None of the latter timestamps automatically supplies a survey year. A source map's approval number applies to that original object, not automatically to an edited thematic map.

## Jiangsu hydrology sample

The original session downloaded the [hydrology archive](https://zrzy.jiangsu.gov.cn/jsbzdt/dtll/sxb.rar) from the Jiangsu catalog. The [preview page](https://zrzy.jiangsu.gov.cn/jsbzdt/dtll/sxb/index.html) used a legacy Flash viewer, so the downloaded map was inspected locally instead of attempting to enable Flash.

| Attribute | Observed sample |
|---|---|
| Catalog edition | 2025, hydrology map, 1:1,000,000, half-sheet format |
| Catalog update / HTTP modification | 2025-08-27 / 2025-08-28 |
| Retrieval | 2026-11-09 |
| Archive size | 25,532,934 bytes |
| Archive SHA-256 | `6b351391a480d1fd0a96bcf489bd1e7891d4b9ad0d7aae4f1447c0fdd3ea3a1d` |
| Actual member types | One EPS and one JPG |
| Unpacked sizes | EPS: 28,811,402 bytes; JPG: 15,785,074 bytes |
| JPG dimensions | 9295 × 7086 pixels |
| Boundary/seat content | Province and prefecture boundaries; province, prefecture and county-level seat symbols |
| Water content | Grand Canal, rivers, lakes and reservoirs |

The original map's number was observed and recorded as a source identity; it must never be copied as approval of a new thematic map. A county seat is a point symbol, not a county boundary. The sampled legend did not establish a county-boundary layer. Large pixel dimensions cannot recover missing local river detail or a survey-accuracy claim.

A [2026 edition announcement](https://zgjssw.jschina.com.cn/yaowen/202608/t20260829_8590884.shtml) was read, but the specific static archive retrieved remained the 2025 file. Do not rename it “latest 2026” based on that announcement. Find and check the actual new file for a new project.

A separate [older China-map archive](https://zrzy.jiangsu.gov.cn/jsbzdt/dtll/3000qg.rar) contained only JPG. That observation demonstrates that not every archive has EPS; it is not a recommendation to use the older file as the latest national background.

## Choose by actual file content

| Material | Suitable route | Essential check |
|---|---|---|
| JPG/PNG/TIF | Use as an identified image background or a separately designed image workflow | Resolution, complete marginal information and actual geographic reference |
| EPS | Inspect/edit supported graphical structure | Real paths/text/bitmaps; no promise that every feature is independently editable |
| GeoJSON/Shapefile/GeoPackage | Spatial preparation after CRS/source checks | Feature semantics, coordinate definition, attributes and geometry |
| Preview or screenshot only | Obtain the original where possible | Source and limitations; this version does not implement image registration |

EPS can contain vector and raster material; consult the [official Adobe EPS guidance](https://helpx.adobe.com/illustrator/desktop/save-and-export/export-files-to-different-formats/save-artwork-in-eps-format.html). Graphic path coordinates are not automatically geographic coordinates. Obtain suitable sourced spatial data for detailed analytical rivers, shores or county boundaries rather than representing tracing as official original GIS data.

## Access failures and maintenance

Record the failing URL, time, method and actual error. A reasonable retry or another documented official link may help. Do not guess protected download paths, bypass authentication/captchas or change identity to evade an access restriction. Preserve the useful catalog/sample evidence already obtained and clearly identify what remains unavailable.

Update specific records when a new edition is inspected while retaining old file identities for reproducibility. This repository keeps English guidance and indices rather than embedding large government map archives or original-language legal PDFs.
