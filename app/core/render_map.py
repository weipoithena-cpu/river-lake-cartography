"""Render a local river/lake/admin GeoJSON map with measured layout checks.

python app/core/render_map.py --job PROJECT/map_job.json --output-dir PROJECT/output

Only EPSG:4326 longitude/latitude GeoJSON is accepted in this small renderer.
It does not locate monitoring stations, georeference images, download data,
turn collaborative data into an official standard map, or issue map approvals.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys

DEPENDENCY_ERROR = None
try:
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as pe
    from matplotlib.font_manager import FontProperties
    from matplotlib.ft2font import FT2Font
    from matplotlib.lines import Line2D
    from matplotlib.path import Path as MplPath
    from matplotlib.patches import PathPatch, Rectangle, Patch
    from matplotlib.transforms import Bbox
    from pyproj import CRS, Transformer, Geod
    from shapely import transform as transform_coordinates
    from shapely.geometry import shape, box, Point, Polygon
    from shapely.geometry.polygon import orient
    from shapely.ops import unary_union
    from check_environment import select_font
    from cartographic_labels import draw_river_label, line_parts, text_footprint
except Exception as exc:
    DEPENDENCY_ERROR = f"{type(exc).__name__}: {exc}"


ADMIN_STYLES = {
    "province": {"font_size_pt": 19.0, "color": "#7A8991", "weight": "normal", "spacing": " "},
    "city": {"font_size_pt": 16.5, "color": "#71818B", "weight": "normal", "spacing": " "},
    "county": {"font_size_pt": 15.5, "color": "#536A77", "weight": "bold", "spacing": ""},
}
PALETTE = ("#EDF4F7", "#EDF5F1", "#F5F5ED", "#F7F0E8", "#F1EFF7", "#EEF4EC")


def area_name_text(name, spacing=" "):
    """Keep Latin words intact; retain character spacing for other scripts."""
    return name if re.search(r"[A-Za-z]", name) else spacing.join(name)


def validate_job(job):
    """Reject misspelled/unsupported fields before an attractive wrong map."""
    def fields(value, allowed, location):
        if not isinstance(value, dict):
            raise ValueError(f"{location} must be a JSON object.")
        unknown = set(value) - set(allowed)
        if unknown:
            raise ValueError(f"{location} contains unknown fields: {sorted(unknown)}")
    fields(job, {
        "schema_version", "title", "subtitle", "extent_wgs84", "source_crs", "render_crs",
        "lake_file", "rivers_file", "admin_file", "name_fields", "admin_labels",
        "river_labels", "lake_labels", "source_records", "font_path", "output",
        "mask_rivers_by_lakes",
    }, "job")
    if type(job.get("schema_version", 1)) is not int or job.get("schema_version", 1) != 1:
        raise ValueError("schema_version must be the integer 1.")
    for key in ("title", "source_crs"):
        if not isinstance(job.get(key), str) or not job[key].strip():
            raise ValueError(f"{key} must be a nonempty string.")
    for key in ("subtitle", "render_crs", "lake_file", "rivers_file", "admin_file", "font_path"):
        if key in job and job[key] is not None and not isinstance(job[key], str):
            raise ValueError(f"{key} must be a string or null.")
    if "mask_rivers_by_lakes" in job and not isinstance(job["mask_rivers_by_lakes"], bool):
        raise ValueError("mask_rivers_by_lakes must be a JSON boolean (true/false).")
    fields(job.get("name_fields", {}), {"lake", "rivers", "admin"}, "name_fields")
    if any(not isinstance(value, str) or not value for value in job.get("name_fields", {}).values()):
        raise ValueError("Each name_fields entry must be a nonempty field name.")
    fields(job.get("source_records", {}), {"lake", "rivers", "admin"}, "source_records")
    source_fields = {"source_name", "source_url", "year", "license", "authority_status",
                     "attribution", "retrieved_utc", "notes", "version", "metadata_url"}
    for role, record in job.get("source_records", {}).items():
        fields(record, source_fields, f"source_records.{role}")
        for key, value in record.items():
            if key == "year":
                if isinstance(value, bool) or not isinstance(value, (str, int)):
                    raise ValueError(f"source_records.{role}.year must be text or an integer year.")
            elif not isinstance(value, str):
                raise ValueError(f"source_records.{role}.{key} must be a string.")
    fields(job.get("output", {}), {"width_px", "height_px", "dpi"}, "output")
    for key in ("width_px", "height_px"):
        if key in job.get("output", {}) and type(job["output"][key]) is not int:
            raise ValueError(f"output.{key} must be an integer pixel count.")
    output_dpi = job.get("output", {}).get("dpi", 240)
    if (isinstance(output_dpi, bool) or not isinstance(output_dpi, (int, float))
            or not math.isfinite(output_dpi)):
        raise ValueError("output.dpi must be a finite number.")
    permitted = {
        "admin_labels": {"name", "level", "position", "members"},
        "lake_labels": {"name", "position", "font_size_pt"},
        "river_labels": {"source_name", "display_name", "anchor_near", "side",
                         "font_size_pt", "gap_pt", "offset_pt", "name_basis"},
    }
    for group, allowed in permitted.items():
        rows = job.get(group, [])
        if rows is None:
            raise ValueError(f"{group} must be an array; use [] or omit the field when no labels are requested.")
        if not isinstance(rows, list):
            raise ValueError(f"{group} must be an array.")
        for index, row in enumerate(rows):
            location = f"{group}[{index}]"
            fields(row, allowed, location)
            name_key = "source_name" if group == "river_labels" else "name"
            if not isinstance(row.get(name_key), str) or not row[name_key].strip():
                raise ValueError(f"{location}.{name_key} must be a nonempty string.")
            if row[name_key].startswith("<") and row[name_key].endswith(">"):
                raise ValueError(f"{location}.{name_key} still contains a template placeholder.")
            if group == "admin_labels":
                if row.get("level", "county") not in ADMIN_STYLES:
                    raise ValueError(f"{location}.level must be province, city, or county.")
                if "members" in row and (not isinstance(row["members"], list)
                                        or not row["members"]
                                        or any(not isinstance(v, str) or not v for v in row["members"])):
                    raise ValueError(f"{location}.members must be a nonempty array of names.")
            if group == "river_labels":
                if "display_name" in row and (not isinstance(row["display_name"], str)
                                               or not row["display_name"].strip()):
                    raise ValueError(f"{location}.display_name must be a nonempty string.")
                if row.get("display_name", row[name_key]) != row[name_key] and not row.get("name_basis"):
                    raise ValueError(f"{location}: name_basis is required when the displayed river name differs from its source name.")
                if row.get("side", 1) not in (-1, 1) or isinstance(row.get("side", 1), bool):
                    raise ValueError(f"{location}.side must be 1 or -1.")
            for key in ("position", "anchor_near"):
                if row.get(key) is not None:
                    point = row[key]
                    if (not isinstance(point, list) or len(point) != 2
                            or any(isinstance(v, bool) or not isinstance(v, (int, float))
                                   or not math.isfinite(v) for v in point)
                            or not (-180 <= point[0] <= 180 and -90 <= point[1] <= 90)):
                        raise ValueError(f"{location}.{key} requires valid [longitude, latitude] coordinates or null.")
            for key in ("font_size_pt", "gap_pt", "offset_pt"):
                if key in row and (isinstance(row[key], bool)
                                   or not isinstance(row[key], (int, float))
                                   or not math.isfinite(row[key]) or row[key] < 0):
                    raise ValueError(f"{location}.{key} requires a finite, nonnegative number.")
            if row.get("font_size_pt", 12) < 6:
                raise ValueError(f"{location}: Text smaller than 6 pt is not accepted; adjust the extent or selected segment.")


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_save(path, value):
    temporary = Path(path).with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
                         encoding="utf-8")
    temporary.replace(path)


def parts(geometry, kind):
    if geometry.is_empty:
        return
    if geometry.geom_type == kind:
        yield geometry
    elif hasattr(geometry, "geoms"):
        for child in geometry.geoms:
            yield from parts(child, kind)


def plot_polygons(ax, geometry, **style):
    for polygon in parts(geometry, "Polygon"):
        polygon = orient(polygon, sign=1)
        vertices, codes = [], []
        for ring in (polygon.exterior, *polygon.interiors):
            coordinates = list(ring.coords)
            vertices.extend(coordinates)
            codes.extend([MplPath.MOVETO] + [MplPath.LINETO] * (len(coordinates) - 2)
                         + [MplPath.CLOSEPOLY])
        ax.add_patch(PathPatch(MplPath(vertices, codes), **style))


def plot_lines(ax, geometry, **style):
    for line in line_parts(geometry):
        ax.plot(*line.xy, **style)


def resolve_path(job_directory, value):
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (job_directory / path).resolve()


def source_record(job, role, errors, warnings):
    record = job.get("source_records", {}).get(role)
    if not isinstance(record, dict):
        errors.append(f"{role}: missing source_records entry.")
        return {}
    for field in ("source_name", "source_url", "year", "license", "authority_status"):
        value = record.get(field)
        if value is None or not str(value).strip() or "<" in str(value):
            errors.append(f"{role}: source field {field} must contain actual metadata.")
    declared = str(record.get("source_name", "")).lower()
    authority = str(record.get("authority_status", "")).lower()
    if ("openstreetmap" in declared or declared.strip() == "osm") and authority in {
            "\u6807\u51c6\u5730\u56fe", "\u5b98\u65b9\u6807\u51c6\u5730\u56fe", "official_standard_map", "official_standard", "official"}:
        errors.append(f"{role}: OpenStreetMap data must not be described as an official standard map.")
    if any(token in str(record.get("year", "")).casefold()
           for token in ("\u672a\u6ce8\u660e", "\u4e0d\u660e", "unknown", "not specified", "not stated")):
        warnings.append(f"{role}: The survey year is recorded as unknown; the retrieval date is not a survey date.")
    return record


def load_layer(job, directory, role, qa, errors, warnings):
    filename = job.get(role + "_file")
    if not filename:
        qa["layers"][role] = {"provided": False, "feature_count": 0}
        return []
    path = resolve_path(directory, filename)
    metadata = source_record(job, role, errors, warnings)
    report = {"provided": True, "file": str(path), "source_record": metadata,
              "source_crs_declared": job["source_crs"]}
    qa["layers"][role] = report
    if not path.is_file():
        errors.append(f"{role}: file does not exist: {path}")
        return []
    report.update({"sha256": file_hash(path), "bytes": path.stat().st_size})
    try:
        content = json.loads(path.read_text(encoding="utf-8-sig"))
        if content.get("type") == "Feature":
            features = [content]
        elif content.get("type") == "FeatureCollection":
            features = content.get("features", [])
        else:
            raise ValueError("A GeoJSON FeatureCollection or Feature is required.")
        embedded = content.get("crs", {}).get("properties", {}).get("name")
        if embedded and not CRS.from_user_input(embedded).equals(
                CRS.from_epsg(4326), ignore_axis_order=True):
            raise ValueError("The declared file CRS differs from the required EPSG:4326.")
    except Exception as exc:
        errors.append(f"{role}: cannot read GeoJSON: {exc}")
        return []
    field = job.get("name_fields", {}).get(role, "name")
    expected = {"lake": {"Polygon", "MultiPolygon"},
                "admin": {"Polygon", "MultiPolygon"},
                "rivers": {"LineString", "MultiLineString"}}[role]
    result, invalid, empty, unnamed = [], [], [], 0
    for index, feature in enumerate(features):
        try:
            geometry = shape(feature.get("geometry"))
            if geometry.is_empty:
                empty.append(index)
                continue
            if geometry.geom_type not in expected:
                raise ValueError(f"Unsupported geometry type {geometry.geom_type}")
            if not geometry.is_valid:
                raise ValueError("Invalid source geometry; inspect and repair it first. Boundaries are not changed automatically.")
            west, south, east, north = geometry.bounds
            if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
                raise ValueError("Coordinate bounds are inconsistent with EPSG:4326 longitude/latitude.")
            raw_name = (feature.get("properties") or {}).get(field)
            name = "" if raw_name is None else str(raw_name).strip()
            unnamed += not bool(name)
            result.append({"index": index, "name": name, "geometry": geometry,
                           "properties": feature.get("properties") or {},
                           "feature_id": feature.get("id")})
        except Exception as exc:
            invalid.append({"feature_index": index, "reason": str(exc)})
    report.update({"feature_count": len(features), "accepted_feature_count": len(result),
                   "empty_feature_indices": empty, "invalid_features": invalid,
                   "unnamed_feature_count": unnamed, "name_field": field,
                   "geometry_types": sorted({entry["geometry"].geom_type for entry in result})})
    if invalid:
        errors.append(f"{role}: {len(invalid)} features failed the geometry/coordinate checks.")
    if empty:
        warnings.append(f"{role}: Skipped {len(empty)} empty geometries.")
    if not result:
        errors.append(f"{role}: No usable geometry.")
    return result


def choose_crs(extent, requested):
    west, south, east, north = extent
    if east - west > 12 or north - south > 10:
        raise ValueError("Extent exceeds this local template; national or large-basin maps need a dedicated projection and layout workflow.")
    if requested in (None, "", "auto_utm"):
        if south < -80 or north > 84 or south < 0 < north:
            raise ValueError("This extent is unsuitable for automatic single-zone UTM; specify an appropriate projection.")
        zone = lambda lon: min(60, max(1, int(math.floor((lon + 180) / 6)) + 1))
        first, last = zone(west + 1e-8), zone(east - 1e-8)
        if first != last or east - west > 6 or north - south > 6:
            raise ValueError("Extent crosses UTM zones or is too large; choose a suitable projection and specify render_crs.")
        code = (32600 if (south + north) / 2 >= 0 else 32700) + first
        return CRS.from_epsg(code), "auto_utm_single_zone"
    crs = CRS.from_user_input(requested)
    if not crs.is_projected:
        raise ValueError("render_crs must be a suitable projected CRS; longitude/latitude cannot be used directly for a scale bar.")
    if any(abs(axis.unit_conversion_factor - 1.0) > 1e-8 for axis in crs.axis_info[:2]):
        raise ValueError("This version requires a projected render_crs with metre units.")
    return crs, "explicit_project_crs"


def area_label(ax, area, text, font, style, position, forward, obstacles):
    """Pick a candidate whose complete text box fits its supplied visible area."""
    if area.is_empty or area.area <= 0:
        return None, None, {"status": "unplaced", "reason": "No matching visible polygon within the map extent",
                            "candidate_count_examined": 0}
    renderer = ax.figure.canvas.get_renderer()
    chosen_font = FontProperties(fname=font.get_file(), weight=style["weight"])
    artist = ax.text(0, 0, text, fontproperties=chosen_font,
                     fontsize=style["font_size_pt"], color=style["color"],
                     ha="center", va="center", zorder=10,
                     path_effects=[pe.withStroke(linewidth=1.2, foreground="white")])
    if position is not None:
        candidates = [Point(*forward.transform(float(position[0]), float(position[1])))]
    else:
        polygons = sorted(parts(area, "Polygon"), key=lambda item: item.area, reverse=True)
        candidates = [polygon.representative_point() for polygon in polygons[:6]]
        if area.covers(area.centroid):
            candidates.append(area.centroid)
        x0, y0, x1, y1 = area.bounds
        grid = [Point(x, y) for x in np.linspace(x0, x1, 9)[1:-1]
                for y in np.linspace(y0, y1, 9)[1:-1] if area.covers(Point(x, y))]
        candidates += sorted(grid, key=lambda point: point.distance(area.centroid))
    measured = []
    for point in candidates:
        if not area.covers(point):
            continue
        artist.set_position((point.x, point.y))
        bounds = artist.get_window_extent(renderer).expanded(1.02, 1.05)
        corners = np.array([[bounds.x0, bounds.y0], [bounds.x1, bounds.y0],
                            [bounds.x1, bounds.y1], [bounds.x0, bounds.y1]])
        footprint = Polygon(ax.transData.inverted().transform(corners))
        inside = bool(area.covers(footprint))
        collision = any(bounds.overlaps(obstacle) for obstacle in obstacles)
        measured.append({"anchor": [point.x, point.y], "whole_text_inside_area": inside,
                         "overlap_with_reserved_items": collision})
        if inside and not collision:
            return artist, bounds, {
                "status": "placed", "anchor_projected_xy": [point.x, point.y],
                "whole_text_inside_visible_area": inside,
                "text_bounds_pixels": list(map(float, bounds.extents)),
                "candidate_count_examined": len(measured),
            }
    artist.remove()
    return None, None, {"status": "unplaced",
                        "reason": "The full label box cannot fit inside the visible polygon while avoiding existing labels and the legend",
                        "candidate_count_examined": len(measured),
                        "candidate_checks": measured[:10]}


def nice_length(value):
    power = 10 ** math.floor(math.log10(value))
    choices = [1, 2, 5, 10]
    return max(factor * power for factor in choices if factor * power <= value)


def wrap_in_pixels(text, renderer, font, maximum_width):
    lines, current = [], ""
    for character in text:
        candidate = current + character
        width = renderer.get_text_width_height_descent(candidate, font, False)[0]
        if current and width > maximum_width:
            lines.append(current)
            current = character
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def make_scale(ax, inverse, font):
    renderer = ax.figure.canvas.get_renderer()
    frame = ax.get_window_extent(renderer)
    p0 = ax.transData.inverted().transform((frame.x0 + .72 * frame.width,
                                           frame.y0 + .065 * frame.height))
    p1 = ax.transData.inverted().transform((frame.x0 + .91 * frame.width, frame.y0))
    geod = Geod(ellps="WGS84")
    a = inverse.transform(*p0)
    b = inverse.transform(float(p1[0]), float(p0[1]))
    available = abs(geod.inv(*a, *b)[2])
    length = nice_length(available * .90)
    low, high = 0.0, float(p1[0] - p0[0])
    for _ in range(40):
        mid = (low + high) / 2
        trial = inverse.transform(float(p0[0] + mid), float(p0[1]))
        actual = abs(geod.inv(*a, *trial)[2])
        if actual < length:
            low = mid
        else:
            high = mid
    width = (low + high) / 2
    height = (ax.get_ylim()[1] - ax.get_ylim()[0]) * .005
    artists = []
    for index in range(2):
        patch = Rectangle((p0[0] + index * width / 2, p0[1]), width / 2, height,
                          facecolor="#647782" if index == 0 else "white",
                          edgecolor="#647782", linewidth=.7, zorder=20)
        ax.add_patch(patch)
        artists.append(patch)
    unit, divisor = ("km", 1000) if length >= 1000 else ("m", 1)
    tick_labels = []
    for fraction, label in ((0, "0"), (.5, f"{length/divisor/2:g}"),
                            (1, f"{length/divisor:g} {unit}")):
        annotation = ax.annotate(label, (p0[0] + fraction * width, p0[1]),
                                   xytext=(0, -4), textcoords="offset points",
                                   ha="center", va="top", fontproperties=font,
                                   fontsize=9, color="#647782", zorder=20,
                                   path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])
        artists.append(annotation)
        tick_labels.append(annotation)
    ax.figure.canvas.draw()
    def ticks_overlap():
        bounds = [a.get_window_extent(renderer).expanded(1.08, 1.02) for a in tick_labels]
        return any(a.overlaps(b) for i, a in enumerate(bounds) for b in bounds[i + 1:])
    if ticks_overlap():
        middle = tick_labels.pop(1)
        artists.remove(middle)
        middle.remove()
    if ticks_overlap():
        tick_labels[0].set_ha("right")
        tick_labels[-1].set_ha("left")
    label_overlap = ticks_overlap()
    endpoint = inverse.transform(float(p0[0] + width), float(p0[1]))
    measured = abs(geod.inv(*a, *endpoint)[2])
    return artists, {"label_distance_m": length, "ellipsoidal_distance_m": measured,
                     "relative_error": abs(measured - length) / length,
                     "tick_label_count": len(tick_labels), "tick_label_overlap": label_overlap}


def make_north(ax, forward, inverse, font):
    frame = ax.get_window_extent(ax.figure.canvas.get_renderer())
    base_pixel = np.array([frame.x0 + .06 * frame.width, frame.y0 + .84 * frame.height])
    base = ax.transData.inverted().transform(base_pixel)
    lon, lat = inverse.transform(*base)
    north = np.asarray(forward.transform(lon, lat + .01))
    tangent = ax.transData.transform(north) - base_pixel
    tangent /= np.linalg.norm(tangent)
    tip_pixel = base_pixel + tangent * 30 * ax.figure.dpi / 72
    tip = ax.transData.inverted().transform(tip_pixel)
    arrow = ax.annotate("", xy=tip, xytext=base,
                        arrowprops={"arrowstyle": "-|>", "mutation_scale": 17,
                                    "lw": 1.3, "color": "#5E707B"}, zorder=20)
    arrow.arrow_patch.set_path_effects([pe.withStroke(linewidth=3.2, foreground="white")])
    label = ax.annotate("N", xy=tip, xytext=(0, 4), textcoords="offset points",
                       ha="center", va="bottom", fontproperties=font, fontsize=11,
                       color="#5E707B", zorder=20,
                       path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])
    bounds = Bbox.from_extents(min(base_pixel[0], tip_pixel[0]) - 12,
                              min(base_pixel[1], tip_pixel[1]) - 4,
                              max(base_pixel[0], tip_pixel[0]) + 12,
                              max(base_pixel[1], tip_pixel[1]) + 22)
    return [arrow, label], bounds


def render(job_path, output_dir, qa):
    errors, warnings = qa["errors"], qa["warnings"]
    if DEPENDENCY_ERROR:
        raise RuntimeError("The runtime is missing a dependency or cannot import it: " + DEPENDENCY_ERROR
                           + "; run check_environment.py.")
    job = json.loads(job_path.read_text(encoding="utf-8-sig"))
    qa["job_sha256"] = file_hash(job_path)
    validate_job(job)
    qa["requested_labels"] = {key: job.get(key, [])
                              for key in ("admin_labels", "river_labels", "lake_labels")}
    if job.get("schema_version", 1) != 1:
        raise ValueError("This version accepts only schema_version=1.")
    if not isinstance(job.get("title"), str) or not job["title"].strip():
        raise ValueError("A nonempty title is required.")
    source = CRS.from_user_input(job.get("source_crs", ""))
    if not source.equals(CRS.from_epsg(4326), ignore_axis_order=True):
        raise ValueError("GeoJSON must explicitly declare source_crs=EPSG:4326 (longitude, latitude).")
    extent = job.get("extent_wgs84")
    if not isinstance(extent, list) or len(extent) != 4 or not all(
            isinstance(value, (int, float)) and math.isfinite(value) for value in extent):
        raise ValueError("extent_wgs84 requires four finite values: [west, south, east, north].")
    west, south, east, north = extent
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Invalid longitude/latitude extent, or the extent crosses the antimeridian.")
    target, crs_method = choose_crs(extent, job.get("render_crs", "auto_utm"))
    qa["crs"] = {"source": source.to_string(), "render": target.to_string(),
                 "render_selection": crs_method, "render_wkt": target.to_wkt(),
                 "projected_units": "metre", "extent_wgs84": extent}
    forward = Transformer.from_crs(source, target, always_xy=True)
    inverse = Transformer.from_crs(target, source, always_xy=True)
    project = lambda geometry: transform_coordinates(
        geometry, lambda coordinates: np.column_stack(
            forward.transform(coordinates[:, 0], coordinates[:, 1])))
    geographic_frame = box(*extent)
    lake = load_layer(job, job_path.parent, "lake", qa, errors, warnings)
    rivers = load_layer(job, job_path.parent, "rivers", qa, errors, warnings)
    admin = load_layer(job, job_path.parent, "admin", qa, errors, warnings)
    if not any((lake, rivers, admin)):
        errors.append("At least one usable lake, river, or administrative-area layer is required.")
    if errors:
        return
    for role, entries in (("lake", lake), ("rivers", rivers), ("admin", admin)):
        for entry in entries:
            clipped = entry["geometry"].intersection(geographic_frame)
            relevant = (list(line_parts(clipped)) if role == "rivers"
                        else list(parts(clipped, "Polygon")))
            entry["visible"] = unary_union(relevant)
            entry["projected"] = project(entry["visible"])
        visible = [entry for entry in entries if not entry["visible"].is_empty]
        qa["layers"][role]["visible_feature_count"] = len(visible)
        if entries and not visible:
            errors.append(f"{role}: No visible features in the specified extent.")
    if errors:
        return
    font_path = job.get("font_path")
    font_path = resolve_path(job_path.parent, font_path) if font_path else None
    font_path = select_font(font_path)
    font = FontProperties(fname=str(font_path))
    qa["font"] = {"file": str(font_path), "sha256": file_hash(font_path)}
    output = job.get("output", {})
    width, height, dpi = (int(output.get("width_px", 3840)),
                          int(output.get("height_px", 2160)), float(output.get("dpi", 240)))
    if not (1280 <= width <= 7680 and 720 <= height <= 4320 and 72 <= dpi <= 600):
        raise ValueError("Output limits: width 1280-7680 px, height 720-4320 px, and 72-600 DPI.")
    if abs(width / height - 16 / 9) > 1e-6:
        raise ValueError("This template supports 16:9; other aspect ratios need a dedicated layout.")
    qa["output_request"] = {"width_px": width, "height_px": height, "dpi": dpi}
    plt.rcParams.update({"axes.unicode_minus": False, "svg.fonttype": "path"})
    figure = plt.figure(figsize=(width / dpi, height / dpi), dpi=100, facecolor="white")
    qa["layout_canvas_dpi"] = float(figure.dpi)
    qa["layout_canvas_size_px"] = list(figure.canvas.get_width_height())
    figure.text(.048, .938, job["title"], fontproperties=font, fontsize=26,
                color="#153B5A", weight="bold", va="center")
    figure.text(.049, .888, job.get("subtitle", "Rivers, lakes and administrative areas"),
                fontproperties=font, fontsize=12, color="#687F8C")
    figure.add_artist(Line2D([.05, .95], [.851, .851], color="#E0E9ED",
                             linewidth=1, transform=figure.transFigure))
    ax = figure.add_axes([.05, .155, .90, .66])
    # Densify the frame edges before projection; no assumption of parallel
    # longitude/latitude edges in the projected coordinate system.
    xs = np.linspace(west, east, 21)
    ys = np.linspace(south, north, 21)
    ring = [(x, south) for x in xs] + [(east, y) for y in ys] + [
        (x, north) for x in xs[::-1]] + [(west, y) for y in ys[::-1]]
    frame = project(Polygon(ring))
    xmin, ymin, xmax, ymax = frame.bounds
    if not np.isfinite([xmin, ymin, xmax, ymax]).all():
        raise ValueError("The selected projection produced non-finite map coordinates.")
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.set_facecolor("#FCFDFD")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#D5E1E7")
        spine.set_linewidth(.8)
    for index, entry in enumerate(admin):
        plot_polygons(ax, entry["projected"], facecolor=PALETTE[index % len(PALETTE)],
                      edgecolor="#B6C3CA", linewidth=.75, zorder=1)
    for entry in lake:
        plot_polygons(ax, entry["projected"], facecolor="#BBDDEA", edgecolor="#69A6BD",
                      linewidth=1.0, zorder=3)
    for entry in admin:
        for polygon in parts(entry["projected"], "Polygon"):
            plot_lines(ax, polygon.boundary, color="#B6C3CA", linewidth=.65, zorder=4)
    water_union = unary_union([entry["visible"] for entry in lake])
    mask_water = bool(job.get("mask_rivers_by_lakes", True))
    visible_rivers = {}
    drawn_rivers = 0
    masked_river_names = []
    focus = {item.get("source_name") for item in job.get("river_labels", [])}
    for entry in rivers:
        visible = entry["visible"].difference(water_union) if mask_water else entry["visible"]
        if visible.is_empty:
            if entry["name"]:
                masked_river_names.append(entry["name"])
            continue
        geometry = project(visible)
        plot_lines(ax, geometry, color="#3F8AAE" if entry["name"] in focus else "#96BFCF",
                   linewidth=1.55 if entry["name"] in focus else .8,
                   solid_capstyle="round", zorder=5)
        drawn_rivers += 1
        visible_rivers.setdefault(entry["name"], []).append(geometry)
    qa["layers"]["rivers"].update({"drawn_feature_count": drawn_rivers,
                                   "mask_rivers_by_lakes": mask_water,
                                   "fully_masked_names": sorted(set(masked_river_names))})
    # Province boundaries are only the exact common boundary of supplied,
    # explicitly grouped admin features. No missing boundary is interpolated.
    admin_specs = job.get("admin_labels", [])
    admin_by_name = {}
    for entry in admin:
        admin_by_name.setdefault(entry["name"], []).append(entry["projected"])
    admin_areas = {}
    for index, spec in enumerate(admin_specs):
        level = spec.get("level", "county")
        if level not in ADMIN_STYLES:
            errors.append(f"Administrative label {spec.get('name')}: level must be province, city, or county.")
            continue
        names = spec.get("members") or [spec.get("name")]
        missing = [name for name in names if name not in admin_by_name]
        if missing:
            errors.append(f"Administrative label {spec.get('name')}: Matching polygon not found: {missing}.")
            continue
        admin_areas[index] = unary_union([geometry for name in names
                                         for geometry in admin_by_name[name]])
    province_areas = [admin_areas[index] for index, spec in enumerate(admin_specs)
                      if spec.get("level") == "province" and index in admin_areas
                      and not admin_areas[index].is_empty]
    province_lines = []
    for index, first in enumerate(province_areas):
        for second in province_areas[index + 1:]:
            shared = first.boundary.intersection(second.boundary)
            if shared.length > 0:
                province_lines.append(shared)
                plot_lines(ax, shared, color="#78848E", linewidth=1.05,
                           linestyle=(0, (5, 3)), zorder=6)
    qa["derived_province_boundary"] = {
        "basis": "exact_common_boundaries_of_supplied_admin_members",
        "length_m": float(sum(geometry.length for geometry in province_lines))}
    legend_handles, legend_labels = [], []
    if lake:
        legend_handles.append(Patch(facecolor="#BBDDEA", edgecolor="#69A6BD", label="Lake outline"))
    if drawn_rivers:
        legend_handles.append(Line2D([0], [0], color="#3F8AAE", lw=1.55, label="River / canal"))
    if province_lines:
        legend_handles.append(Line2D([0], [0], color="#78848E", lw=1.05,
                                     linestyle=(0, (5, 3)), label="Province boundary"))
    if admin:
        legend_handles.append(Line2D([0], [0], color="#B6C3CA", lw=.75, label="Administrative boundary"))
    legend_labels = [item.get_label() for item in legend_handles]
    legend = ax.legend(handles=legend_handles, loc="lower left", bbox_to_anchor=(.025, .035),
                       bbox_transform=ax.transAxes, title="Legend", ncol=1,
                       frameon=True, fancybox=False, facecolor="white", framealpha=1.0,
                       edgecolor="#DCE6EA", borderpad=.9, labelspacing=.65,
                       prop=FontProperties(fname=str(font_path), size=10),
                       title_fontproperties=FontProperties(fname=str(font_path), size=11))
    legend.set_zorder(30)
    figure.canvas.draw()
    scale_artists, scale_report = make_scale(ax, inverse, font)
    north_artists, north_bounds = make_north(ax, forward, inverse, font)
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    obstacles = [legend.get_window_extent(renderer).expanded(1.05, 1.05), north_bounds]
    obstacles += [artist.get_window_extent(renderer).expanded(1.05, 1.05)
                  for artist in scale_artists]
    text_items = []
    qa["lake_labels"], qa["admin_labels"], qa["river_labels"] = [], [], []
    for index, spec in enumerate(admin_specs):
        if index not in admin_areas:
            qa["admin_labels"].append({
                "name": spec.get("name"), "level": spec.get("level", "county"),
                "status": "unplaced", "reason": "No complete matching administrative polygon or member polygons were found",
                "members": spec.get("members") or [spec.get("name")]})
    # Automatically try names that are present in lake data. Explicitly
    # requested lake_labels are also supported and are mandatory.
    lake_specs = job.get("lake_labels")
    explicit_lake_names = lake_specs is not None
    if lake_specs is None:
        lake_specs = [{"name": name} for name in dict.fromkeys(
            entry["name"] for entry in lake if entry["name"] and not entry["visible"].is_empty)]
    for spec in lake_specs:
        name = spec.get("name", "")
        matches = [entry["projected"] for entry in lake if entry["name"] == name]
        if not matches:
            record = {"name": name, "status": "unplaced", "reason": "Matching lake polygon not found"}
            qa["lake_labels"].append(record)
            (errors if explicit_lake_names else warnings).append(f"Lake label {name}: Lake polygon not found.")
            continue
        area = unary_union(matches)
        style = {"font_size_pt": float(spec.get("font_size_pt", 20)),
                 "weight": "bold", "color": "#327C99"}
        artist, bounds, record = area_label(ax, area, area_name_text(name), font, style,
                                           spec.get("position"), forward, obstacles)
        record.update({"name": name, "explicitly_requested": explicit_lake_names})
        qa["lake_labels"].append(record)
        if artist is None:
            (errors if explicit_lake_names else warnings).append(f"Lake label {name}: Could not place the label.")
        else:
            obstacles.append(bounds)
            text_items.append({"kind": "lake", "name": name, "artist": artist, "area": area})
    # Large-area labels go first so default county label positions can avoid
    # them. An explicit position remains an explicit position, not a silent move.
    order = {"province": 0, "city": 1, "county": 2}
    for index in sorted(admin_areas, key=lambda item: order[admin_specs[item].get("level", "county")]):
        spec, area = admin_specs[index], admin_areas[index]
        name, level = spec["name"], spec.get("level", "county")
        style = dict(ADMIN_STYLES[level])
        text = area_name_text(name, style["spacing"])
        artist, bounds, record = area_label(ax, area, text, font, style,
                                           spec.get("position"), forward, obstacles)
        record.update({"name": name, "level": level, "style": style,
                       "members": spec.get("members") or [name],
                       "geometry_basis": "supplied_visible_admin_features"})
        qa["admin_labels"].append(record)
        if artist is None:
            errors.append(f"Administrative label {name}: Could not place the full label inside its visible administrative area.")
        else:
            record["position_wgs84"] = list(inverse.transform(*record["anchor_projected_xy"]))
            obstacles.append(bounds)
            text_items.append({"kind": "admin", "name": name, "artist": artist, "area": area})
    for spec in job.get("river_labels", []):
        source_name = spec.get("source_name", "")
        display_name = spec.get("display_name") or source_name
        lines = visible_rivers.get(source_name, [])
        if not lines:
            record = {"source_name": source_name, "name": display_name, "status": "unplaced",
                      "reason": "No matching river line is visible after extent clipping and waterbody masking", "leader_line_count": 0}
            qa["river_labels"].append(record)
            errors.append(f"Requested river label {display_name}: No visible river line; could not place the label.")
            continue
        geometry = unary_union(lines)
        near = spec.get("anchor_near")
        if near is None:
            longest = max(line_parts(geometry), key=lambda line: line.length)
            point = longest.interpolate(.5, normalized=True)
            near_xy = (point.x, point.y)
        else:
            near_xy = forward.transform(*near)
        artists, record = draw_river_label(
            ax, geometry, near_xy, display_name, font,
            size=float(spec.get("font_size_pt", 12)), gap_pt=float(spec.get("gap_pt", 2)),
            offset_pt=float(spec.get("offset_pt", 7)), side=int(spec.get("side", 1)),
            obstacles=obstacles)
        record["source_name"] = source_name
        record["projected_distance_unit"] = "metre"
        if spec.get("name_basis"):
            record["name_basis"] = spec["name_basis"]
        qa["river_labels"].append(record)
        if not artists:
            errors.append(f"Requested river label {display_name}: Could not place the label while satisfying path, reading-order, and collision rules.")
        for artist in artists:
            text_items.append({"kind": "river", "name": display_name, "artist": artist})
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        obstacles += [artist.get_window_extent(renderer).expanded(1.05, 1.05) for artist in artists]
    # Sources are supplied facts, not an automated certification of authority.
    sources = [qa["layers"][role].get("source_record", {}) for role in ("lake", "rivers", "admin")
               if qa["layers"][role].get("provided")]
    source_text = "Sources: " + "; ".join(dict.fromkeys(
        f"{record.get('attribution') or record.get('source_name')} ({record.get('year')})"
        for record in sources))
    footer_font = FontProperties(fname=str(font_path), size=8.5)
    source_lines = wrap_in_pixels(source_text, renderer, footer_font, figure.bbox.width * .90)
    qa["source_attribution_full_text"] = source_text
    qa["source_attribution_required_lines"] = len(source_lines)
    if len(source_lines) > 3:
        errors.append("Attribution exceeds the footer capacity; adjust the layout. A completed map must not omit attribution.")
        source_lines = source_lines[:2] + ["[Incomplete attribution: layout diagnostic only]"]
    for index, line in enumerate(source_lines):
        figure.text(.05, .105 - index * .023, line, fontproperties=font, fontsize=8.5,
                    color="#7C8E99")
    nature = "Data status: " + "; ".join(dict.fromkeys(record["authority_status"] for record in sources))
    nature_lines = wrap_in_pixels(nature, renderer, footer_font, figure.bbox.width * .90)
    qa["source_nature_full_text"] = nature
    if len(nature_lines) > 1:
        warnings.append("Data-status text exceeds one line; the map uses a brief note and the full record is retained.")
        nature = "See the source records for data status and versions."
    figure.text(.05, .025, nature,
                fontproperties=font, fontsize=8.5, color="#7C8E99")
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    frame_pixels = ax.get_window_extent(renderer)
    legend_bounds = legend.get_window_extent(renderer)
    legend_inside = bool(frame_pixels.contains(legend_bounds.x0, legend_bounds.y0)
                         and frame_pixels.contains(legend_bounds.x1, legend_bounds.y1))
    legend_lower_left = bool(legend_bounds.x1 < frame_pixels.x0 + frame_pixels.width / 2
                             and legend_bounds.y1 < frame_pixels.y0 + frame_pixels.height / 2)
    violations, overlaps, admin_footprints = [], [], []
    for item in text_items:
        bounds = item["artist"].get_window_extent(renderer)
        if not (frame_pixels.contains(bounds.x0, bounds.y0) and
                frame_pixels.contains(bounds.x1, bounds.y1)):
            violations.append({"name": item["name"], "issue": "text_outside_frame"})
        if bounds.overlaps(legend_bounds):
            violations.append({"name": item["name"], "issue": "legend_overlaps_text"})
        if item["kind"] == "admin":
            corners = np.array([[bounds.x0, bounds.y0], [bounds.x1, bounds.y0],
                                [bounds.x1, bounds.y1], [bounds.x0, bounds.y1]])
            footprint = Polygon(ax.transData.inverted().transform(corners))
            inside = bool(item["area"].covers(footprint))
            admin_footprints.append({"name": item["name"], "whole_text_inside_visible_area": inside})
            if not inside:
                violations.append({"name": item["name"], "issue": "admin_text_outside_area"})
    footprints = [text_footprint(item["artist"], renderer) for item in text_items]
    for index, first in enumerate(text_items):
        for second_index, second in enumerate(text_items[index + 1:], index + 1):
            if footprints[index].intersection(footprints[second_index]).area > 1e-6:
                overlaps.append({"first": first["name"], "second": second["name"],
                                 "first_text": first["artist"].get_text(),
                                 "second_text": second["artist"].get_text()})
    river_artists = [item["artist"] for item in text_items if item["kind"] == "river"]
    leader_count = sum(getattr(artist, "arrow_patch", None) is not None for artist in river_artists)
    qa["layout_checks"] = {
        "legend_inside_map": legend_inside, "legend_lower_left": legend_lower_left,
        "legend_entries": legend_labels, "text_violations": violations,
        "text_overlap_pairs": overlaps, "admin_footprints": admin_footprints,
        "text_overlap_geometry": "rotated_text_rectangles_in_display_pixels",
        "river_leader_line_count": leader_count,
        "north_arrow_basis": "projected_true_north_at_arrow_location",
        "scale": scale_report,
    }
    qa["label_counts"] = {
        "requested_admin": len(admin_specs),
        "placed_admin": sum(record["status"] == "placed" for record in qa["admin_labels"]),
        "requested_rivers": len(job.get("river_labels", [])),
        "placed_rivers": sum(record["status"] == "placed" for record in qa["river_labels"]),
        "requested_lakes": len(job.get("lake_labels", [])),
        "placed_requested_lakes": sum(record["status"] == "placed"
                                      and record.get("explicitly_requested", False)
                                      for record in qa["lake_labels"]),
        "automatic_lake_label_candidates": len(lake_specs) if not explicit_lake_names else 0,
        "placed_lake_labels_total": sum(record["status"] == "placed" for record in qa["lake_labels"]),
    }
    if not legend_inside or not legend_lower_left:
        errors.append("The legend is not wholly inside the lower-left part of the map frame.")
    if violations or overlaps or leader_count:
        errors.append("Layout checks detected out-of-frame text, collisions, overlaps, or river-name leader lines.")
    if scale_report["relative_error"] > 0.001:
        errors.append("Scale-bar error relative to the ellipsoidal distance exceeds 0.1%.")
    if scale_report.get("tick_label_overlap"):
        errors.append("Scale-bar tick labels overlap; adjust the extent or layout.")
    # Verify font coverage for actual requested names and title.
    face = FT2Font(str(font_path))
    characters = set(job["title"] + "".join(item["artist"].get_text() for item in text_items))
    missing_glyphs = sorted(char for char in characters if not char.isspace()
                            and face.get_char_index(ord(char)) == 0)
    qa["font"]["missing_glyphs"] = missing_glyphs
    if missing_glyphs:
        errors.append("The selected font is missing requested glyphs: " + "".join(missing_glyphs))
    if errors:
        figure.text(.95, .895, "DIAGNOSTIC PREVIEW: checks failed", fontproperties=font, fontsize=12,
                    color="#AD4339", ha="right",
                    bbox={"facecolor": "#FFF2EF", "edgecolor": "none", "pad": 4})
    description = "Source records are supplied in qa.json; this output is a local thematic map."
    temporaries = {}
    for extension in ("png", "svg"):
        temporary = output_dir / f".render.{qa['run_id']}.{extension}"
        figure.savefig(temporary, dpi=dpi, facecolor="white",
                       metadata={"Description": description})
        temporaries[extension] = temporary
    actual_width, actual_height = struct.unpack(">II", temporaries["png"].read_bytes()[16:24])
    qa["image_size_px_measured"] = [actual_width, actual_height]
    if [actual_width, actual_height] != [width, height]:
        errors.append("Measured output pixel dimensions differ from the job specification.")
        figure.text(.95, .895, "DIAGNOSTIC PREVIEW: incorrect output size", fontproperties=font, fontsize=12,
                    color="#AD4339", ha="right",
                    bbox={"facecolor": "#FFF2EF", "edgecolor": "none", "pad": 4})
        for temporary in temporaries.values():
            figure.savefig(temporary, dpi=dpi, facecolor="white",
                           metadata={"Description": description})
    # Promote files only after checking the newly rendered PNG. A failed run
    # never replaces a previous successful map.png/map.svg.
    stem = "diagnostic_preview" if errors else "map"
    for extension, temporary in temporaries.items():
        filename = output_dir / f"{stem}.{extension}"
        temporary.replace(filename)
        qa["outputs"].append({"file": str(filename), "sha256": file_hash(filename),
                              "kind": "diagnostic" if errors else "map"})
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    job_path = args.job.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    qa = {
        "schema_version": 1,
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "job_file": str(job_path), "renderer_sha256": file_hash(__file__),
        "support_script_sha256": {
            name: file_hash(Path(__file__).with_name(name))
            for name in ("cartographic_labels.py", "check_environment.py")},
        "source_records_authority": "supplied_by_job_not_certified_by_renderer",
        "status": "running", "layers": {}, "errors": [], "warnings": [], "outputs": [],
    }
    if not DEPENDENCY_ERROR:
        import shapely
        import pyproj
        qa["versions"] = {"python": sys.version.split()[0], "numpy": np.__version__,
                          "matplotlib": matplotlib.__version__, "shapely": shapely.__version__,
                          "pyproj": pyproj.__version__}
    try:
        render(job_path, output_dir, qa)
    except Exception as exc:
        qa["errors"].append(f"{type(exc).__name__}: {exc}")
    qa["status"] = ("failed" if qa["errors"] else
                    "completed_with_warnings" if qa["warnings"] else "completed")
    qa["missing_or_unplaced_labels"] = [
        {"kind": kind, **record}
        for kind, key in (("admin", "admin_labels"), ("river", "river_labels"), ("lake", "lake_labels"))
        for record in qa.get(key, []) if record.get("status") != "placed"]
    if qa["errors"]:
        qa["prior_success_files_not_updated"] = [
            str(output_dir / name) for name in ("map.png", "map.svg")
            if (output_dir / name).exists()
            and not any(item["file"] == str(output_dir / name) for item in qa["outputs"])]
    json_save(output_dir / "qa.json", qa)
    print(json.dumps({"status": qa["status"], "qa": str(output_dir / "qa.json"),
                      "outputs": [item["file"] for item in qa["outputs"]],
                      "errors": qa["errors"], "warnings": qa["warnings"]},
                     ensure_ascii=False, indent=2))
    return 1 if qa["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
