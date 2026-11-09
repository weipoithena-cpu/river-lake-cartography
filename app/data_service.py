"""Bounded, traceable data preparation for River Lake Cartography Desktop.

The online mode produces an OpenStreetMap working draft.  It is not a survey,
an official administrative-boundary service, or a hydrological flow model.
All network requests are explicit, serial, cached, and use an identifying UA.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from pyproj import CRS, Geod, Transformer
import numpy as np
from shapely import transform as transform_coordinates
from shapely.geometry import LineString, Polygon, box, mapping, shape
from shapely.ops import polygonize, unary_union, linemerge, polylabel

PHOTON_ENDPOINT = "https://photon.komoot.io/api/"
OVERPASS_ENDPOINT = "https://overpass.private.coffee/api/interpreter"
USER_AGENT = "RiverLakeCartographyDesktop/1.0 (local user-triggered cartographic research)"
NETWORK_POLICY_URLS = {
    "photon": "https://github.com/komoot/photon/blob/master/README.md",
    "overpass": "https://wiki.openstreetmap.org/wiki/Overpass_API",
    "data_license": "https://www.openstreetmap.org/copyright",
    "china_admin_levels": "https://wiki.openstreetmap.org/wiki/China/Boundaries",
}
_network_lock = threading.Lock()
_last_request = 0.0
_geod = Geod(ellps="WGS84")
MAX_BYTES = 40 * 1024 * 1024
MAX_FEATURES = 14000
ROLES = ("lake", "rivers", "admin")


class DataServiceError(ValueError):
    """An actionable user-facing preparation or network error."""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temp.replace(path)


def _notify(callback, percent, message):
    if callback:
        callback(percent, message)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _endpoint(kind, endpoints=None):
    configured = endpoints or {}
    default = PHOTON_ENDPOINT if kind == "photon" else OVERPASS_ENDPOINT
    value = configured.get(kind) or os.environ.get("RIVERLAKE_" + kind.upper() + "_URL") or default
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise DataServiceError("Data service URLs must use HTTPS without embedded credentials.")
    return value


def _request_json(url, cache_dir, post_data=None, timeout=100, max_bytes=MAX_BYTES):
    """Read once; do not retry a busy service or bypass its rate limiting."""
    global _last_request
    key = hashlib.sha256(url.encode() + (post_data or b"")).hexdigest()
    cache = Path(cache_dir) / (key + ".json")
    meta = Path(cache_dir) / (key + ".meta.json")
    if cache.is_file():
        try:
            return json.loads(cache.read_text(encoding="utf-8")), json.loads(meta.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    request = urllib.request.Request(url, data=post_data, headers={
        "User-Agent": USER_AGENT, "Accept": "application/json", "Accept-Language": "en",
        **({"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"} if post_data else {}),
    })
    try:
        with _network_lock:
            delay = 1.25 - (time.monotonic() - _last_request)
            if delay > 0:
                time.sleep(delay)
            _last_request = time.monotonic()
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content = response.read(max_bytes + 1)
                if len(content) > max_bytes:
                    raise DataServiceError("The response exceeds the download limit. Reduce the map extent or import local GeoJSON.")
    except urllib.error.HTTPError as exc:
        if exc.code in (429, 406):
            raise DataServiceError("The public data service is rate limited. Wait at least 30 seconds before retrying manually, or use the example or local data.") from exc
        if exc.code in (502, 503, 504):
            raise DataServiceError("The public data service is busy. Retry later, reduce the extent, or import local data.") from exc
        raise DataServiceError(f"The data service returned HTTP {exc.code}. Check your connection or retry later.") from exc
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        raise DataServiceError("The public data service is unreachable or timed out. Check your connection. The offline example and local GeoJSON import remain available.") from exc
    try:
        result = json.loads(content.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise DataServiceError("The data service did not return valid JSON. Retry later.") from exc
    record = {"url": url, "retrieved_utc": _now(), "sha256": hashlib.sha256(content).hexdigest(),
              "request_method": "POST" if post_data else "GET", "bytes": len(content)}
    if isinstance(result, dict) and result.get("remark"):
        raise DataServiceError("The data service did not complete the query: " + str(result["remark"])[:400])
    _save(cache, result)
    _save(meta, record)
    return result, record


def _number(value):
    if isinstance(value, bool):
        raise DataServiceError("Longitude and latitude must be numeric.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DataServiceError("Longitude and latitude must be numeric.") from exc
    if not math.isfinite(number):
        raise DataServiceError("Longitude and latitude must be finite numbers.")
    return number


def validate_bbox(bbox, *, online=False):
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise DataServiceError("Provide the map extent as [west longitude, south latitude, east longitude, north latitude].")
    west, south, east, north = [_number(v) for v in bbox]
    if not (-180 <= west < east <= 180 and -80 <= south < north <= 84):
        raise DataServiceError("Invalid extent: west must be less than east and south less than north. This edition supports local maps from latitude -80 to 84 degrees.")
    if east-west > 12 or north-south > 10:
        raise DataServiceError("This extent exceeds the local mapping scope. Reduce it or use a workflow designed for large areas.")
    if online:
        width = abs(_geod.inv(west, (south+north)/2, east, (south+north)/2)[2]) / 1000
        height = abs(_geod.inv((west+east)/2, south, (west+east)/2, north)[2]) / 1000
        if east-west > 3 or north-south > 3 or max(width, height) > 220 or width*height > 30000:
            raise DataServiceError("Online drafts are limited to local extents: at most 3 degrees per axis, 220 km per side, and approximately 30,000 square kilometres. Reduce the extent or import local data.")
    return [west, south, east, north]


def _padded_bbox(bbox, fraction=0.12):
    w, s, e, n = bbox
    padx, pady = max((e-w)*fraction, .015), max((n-s)*fraction, .015)
    return [max(-180, w-padx), max(-79.99, s-pady), min(180, e+padx), min(83.99, n+pady)]


def _project(geometry, transformer):
    return transform_coordinates(geometry, lambda coordinates: np.column_stack(
        transformer.transform(coordinates[:, 0], coordinates[:, 1])))


def search_places(query, cache_dir, endpoints=None):
    """Explicit place search via Photon. Never used for autocomplete or bulk lists."""
    query = str(query or "").strip()
    if not 2 <= len(query) <= 160:
        raise DataServiceError("Enter a river, lake, or place name of 2 to 160 characters. Include the city or region where possible.")
    endpoint = _endpoint("photon", endpoints)
    url = endpoint + ("&" if "?" in endpoint else "?") + urllib.parse.urlencode({"q": query, "limit": 8, "lang": "en"})
    data, record = _request_json(url, cache_dir, timeout=35, max_bytes=4*1024*1024)
    results = []
    for feature in data.get("features", []):
        props = feature.get("properties") or {}
        try:
            lon, lat = [_number(v) for v in feature["geometry"]["coordinates"][:2]]
            if not (-180 <= lon <= 180 and -80 < lat < 84):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        extent = props.get("extent")
        inferred = not (isinstance(extent, list) and len(extent) == 4)
        if inferred:
            bbox = [lon-.12, lat-.09, lon+.12, lat+.09]
        else:
            # Photon uses [west, north, east, south], unlike GeoJSON bbox.
            try:
                bbox = [_number(extent[0]), _number(extent[3]), _number(extent[2]), _number(extent[1])]
                if bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
                    raise DataServiceError("zero extent")
                bbox = _padded_bbox(bbox)
            except DataServiceError:
                bbox, inferred = [lon-.12, lat-.09, lon+.12, lat+.09], True
        names = []
        for key in ("name", "district", "city", "county", "state", "country"):
            value = props.get(key)
            if value and str(value) not in names:
                names.append(str(value))
        osm_type = {"N": "node", "W": "way", "R": "relation"}.get(str(props.get("osm_type")), str(props.get("osm_type", "")))
        results.append({"id": f"{osm_type}/{props.get('osm_id', '')}", "name": ", ".join(names) or query,
                        "short_name": str(props.get("name") or query), "bbox": bbox,
                        "bbox_inferred": inferred, "lon": lon, "lat": lat,
                        "type": str(props.get("osm_value") or props.get("type") or "Place"),
                        "osm_type": osm_type, "osm_id": props.get("osm_id"),
                        "country_code": str(props.get("countrycode") or "").upper(),
                        "provider": "Photon / OpenStreetMap", "source_url": record["url"],
                        "retrieved_utc": record["retrieved_utc"]})
    return results


def _line_coords(points):
    return [[float(p["lon"]), float(p["lat"])] for p in points if p and "lon" in p and "lat" in p]


def _parts(geometry, kinds):
    if geometry.geom_type in kinds:
        yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from _parts(part, kinds)


def _polygon_from_relation(element):
    outer_lines, inner_lines = [], []
    for member in element.get("members", []):
        if member.get("type") != "way":
            continue
        coords = _line_coords(member.get("geometry") or [])
        if len(coords) < 2:
            continue
        target = inner_lines if member.get("role") == "inner" else outer_lines if member.get("role", "") in ("outer", "") else None
        if target is not None:
            target.append(LineString(coords))
    if not outer_lines:
        return None
    polygons = list(polygonize(unary_union(outer_lines)))
    if not polygons:
        return None
    geom = unary_union(polygons)
    if inner_lines:
        holes = list(polygonize(unary_union(inner_lines)))
        if holes:
            geom = geom.difference(unary_union(holes))
    return geom


def overpass_to_layers(data, bbox, admin_scheme="CN"):
    """Convert complete geometries, retaining OSM identifiers and skipped records."""
    frame = box(*bbox)
    layers = {role: {"type": "FeatureCollection", "features": []} for role in ROLES}
    skipped = []
    relation_way_ids = set()
    for element in data.get("elements", []):
        if element.get("type") == "relation" and (element.get("tags") or {}).get("natural") == "water":
            relation_way_ids.update(m.get("ref") for m in element.get("members", []) if m.get("type") == "way")
    for element in data.get("elements", []):
        tags = dict(element.get("tags") or {})
        element_type, osm_id = element.get("type"), element.get("id")
        role = ("admin" if tags.get("boundary") == "administrative" else
                "rivers" if tags.get("waterway") in ("river", "canal") else
                "lake" if (tags.get("natural") == "water" or tags.get("landuse") == "reservoir")
                and tags.get("water") not in ("river", "canal") else None)
        if role is None or (role == "lake" and element_type == "way" and osm_id in relation_way_ids):
            continue
        try:
            if element_type == "relation":
                geom = _polygon_from_relation(element) if role != "rivers" else unary_union([
                    LineString(coords) for m in element.get("members", [])
                    if m.get("type") == "way" and len(coords := _line_coords(m.get("geometry") or [])) >= 2])
            else:
                coords = _line_coords(element.get("geometry") or [])
                if role == "rivers" and len(coords) >= 2:
                    geom = LineString(coords)
                elif role != "rivers" and len(coords) >= 4 and coords[0] == coords[-1]:
                    geom = Polygon(coords)
                else:
                    geom = None
            if geom is None or geom.is_empty or not geom.is_valid:
                raise ValueError("Incomplete or invalid geometry; no inferred lines were added")
            if not geom.intersects(frame):
                continue
            clipped = geom.intersection(frame)
            valid_parts = list(_parts(clipped, {"LineString"} if role == "rivers" else {"Polygon"}))
            if not valid_parts:
                continue
            clipped = unary_union(valid_parts)
            if not clipped.is_valid:
                raise ValueError("Clipped geometry failed validation")
            tags.update({"name": str(tags.get("name:en") or tags.get("name") or tags.get("name:zh") or "").strip(),
                         "osm_type": element_type, "osm_id": osm_id,
                         "osm_edit_timestamp": element.get("timestamp"), "source": "OpenStreetMap"})
            if role == "admin":
                tags["cartography_admin_scheme"] = admin_scheme
            layers[role]["features"].append({"type": "Feature", "id": f"{element_type}/{osm_id}",
                                              "properties": tags, "geometry": mapping(clipped)})
        except (ValueError, TypeError, KeyError) as exc:
            skipped.append({"osm_type": element_type, "osm_id": osm_id, "name": tags.get("name", ""), "reason": str(exc)})
    return layers, skipped


def _source_record(role, supplied=None, *, online=False, retrieved=None):
    supplied = supplied or {}
    result = {
        "source_name": "OpenStreetMap contributors" if online else "User-imported spatial data",
        "source_url": "https://www.openstreetmap.org/copyright" if online else "User-provided files in this project's data_raw directory",
        "year": "Not specified (OSM edit timestamps are not survey dates)" if online else "Not specified",
        "license": "ODbL 1.0" if online else "Terms of use must be confirmed by the data provider",
        "authority_status": "Collaborative open data; working draft requiring authoritative verification of boundaries and names" if online else "User-provided; source authority requires verification",
        "attribution": "© OpenStreetMap contributors" if online else "User-provided data",
    }
    # Importing a file does not establish when its original source was retrieved.
    # Preserve a supplied retrieval date; record local import time separately in
    # data_provenance.json rather than inventing a source retrieval timestamp.
    if retrieved:
        result["retrieved_utc"] = retrieved
    elif online:
        result["retrieved_utc"] = _now()
    allowed = {"source_name", "source_url", "year", "license", "authority_status", "attribution", "retrieved_utc", "notes", "version", "metadata_url"}
    for key, value in supplied.items():
        if key in allowed and value is not None and str(value).strip():
            result[key] = value if key == "year" and isinstance(value, int) else str(value)
    return result


def _normalise_layer(content, role, name_field="name"):
    if not isinstance(content, dict):
        raise DataServiceError(f"The {role} layer must be a GeoJSON object.")
    if content.get("type") == "Feature":
        features = [content]
    elif content.get("type") == "FeatureCollection":
        features = content.get("features")
    else:
        raise DataServiceError(f"The {role} layer must be a GeoJSON FeatureCollection or Feature.")
    if not isinstance(features, list) or not features:
        raise DataServiceError(f"The {role} layer has no features.")
    if len(features) > MAX_FEATURES:
        raise DataServiceError(f"The {role} layer exceeds {MAX_FEATURES} features. Clip it to a local extent first.")
    embedded = (content.get("crs") or {}).get("properties", {}).get("name")
    if embedded:
        try:
            crs_ok = CRS.from_user_input(embedded).equals(CRS.from_epsg(4326), ignore_axis_order=True)
        except Exception as exc:
            raise DataServiceError(f"The coordinate reference system declared for {role} is unrecognized.") from exc
        if not crs_ok:
            raise DataServiceError(f"The {role} layer is not EPSG:4326. Transform its coordinates before importing.")
    normalized = []
    for i, feature in enumerate(features):
        if not isinstance(feature, dict):
            raise DataServiceError(f"Feature {i+1} in {role} has an invalid structure.")
        try:
            geom = shape(feature.get("geometry"))
            expected = {"LineString", "MultiLineString"} if role == "rivers" else {"Polygon", "MultiPolygon"}
            if geom.geom_type not in expected or geom.is_empty or not geom.is_valid:
                raise ValueError("Geometry is empty, invalid, or of an unsupported type")
            w, s, e, n = geom.bounds
            if not all(math.isfinite(v) for v in (w, s, e, n)) or not (-180 <= w <= e <= 180 and -90 <= s <= n <= 90):
                raise ValueError("Coordinate values are outside longitude/latitude ranges")
            props = dict(feature.get("properties") or {})
            name = props.get(name_field)
            if name is None:
                name = props.get("name:en") or props.get("name") or props.get("NAME") or props.get("name:zh") or props.get("\u540d\u79f0") or ""
            props["name"] = str(name).strip()
            normalized.append({"type": "Feature", "id": feature.get("id", i), "properties": props, "geometry": mapping(geom)})
        except (ValueError, TypeError, KeyError) as exc:
            raise DataServiceError(f"Feature {i+1} in {role} failed validation: {exc}. Correct the source data and retry.") from exc
    return {"type": "FeatureCollection", "features": normalized}


def _admin_level(properties):
    explicit = str(properties.get("level") or "")
    if explicit in ("province", "city", "county"):
        return explicit
    mainland_china = (properties.get("cartography_admin_scheme") == "CN" or
                      bool(properties.get("ref:admin:CN")) or
                      str(properties.get("ISO3166-2", "")).startswith("CN-"))
    if mainland_china:
        return {"4": "province", "5": "city", "6": "county"}.get(str(properties.get("admin_level", "")))
    return None


def _suggest_labels(layers, bbox, river_names=None):
    if isinstance(river_names, str):
        river_names = [v.strip() for v in re.split(r"[\n,\uFF0C;\uFF1B]+", river_names) if v.strip()]
    frame = box(*bbox)
    area = frame.area
    grouped = {role: {} for role in ROLES}
    props_by_name = {}
    for role, layer in layers.items():
        for feature in layer.get("features", []):
            name = feature["properties"].get("name", "")
            if name:
                geom = shape(feature["geometry"]).intersection(frame)
                if not geom.is_empty:
                    grouped[role].setdefault(name, []).append(geom)
                    if role == "admin":
                        props_by_name[name] = feature["properties"]
    unions = {role: {n: unary_union(gs) for n, gs in groups.items()} for role, groups in grouped.items()}
    waters = unary_union(list(unions["lake"].values()))
    crs = _projection(bbox)
    if crs == "auto_utm":
        code = (32600 if (bbox[1]+bbox[3])/2 >= 0 else 32700) + min(60, max(1, int(math.floor(((bbox[0]+bbox[2])/2+180)/6))+1))
        crs = f"EPSG:{code}"
    forward = Transformer.from_crs(4326, crs, always_xy=True)
    inverse = Transformer.from_crs(crs, 4326, always_xy=True)
    projected_frame = _project(frame, forward)
    x0,y0,x1,y1 = projected_frame.bounds
    # The renderer's default 3840x2160 @240 dpi makes a 1440x594-pixel layout box at 100 dpi.
    scale = min(1440/max(x1-x0, 1), 594/max(y1-y0, 1))
    def anchor_for(geometry, name, size, spaced=False):
        projected = _project(geometry, forward)
        polygons = sorted(_parts(projected, {"Polygon"}), key=lambda p: p.area, reverse=True)
        width_px = (len(name) + (.3*max(0,len(name)-1) if spaced else 0))*size*100/72*1.08
        height_px = size*100/72*1.30
        dx, dy = width_px/scale/2, height_px/scale/2
        for polygon in polygons[:5]:
            points = [polygon.representative_point()]
            try:
                points.insert(0, polylabel(polygon, tolerance=max(1, min(dx,dy)/12)))
            except Exception:
                pass
            if polygon.covers(polygon.centroid):
                points.append(polygon.centroid)
            for point in points:
                if projected.covers(box(point.x-dx, point.y-dy, point.x+dx, point.y+dy)):
                    return list(inverse.transform(point.x, point.y))
        return None
    lake_rank = sorted(unions["lake"], key=lambda n: unions["lake"][n].area, reverse=True)
    lake_names = [n for n in lake_rank if unions["lake"][n].area >= area*.008][:4]
    admin_rank = sorted(unions["admin"], key=lambda n: unions["admin"][n].area, reverse=True)
    admin_names = [n for n in admin_rank if unions["admin"][n].area >= area*.035][:10]
    if river_names is None or not river_names:
        distances = {}
        for name, geometry in unions["rivers"].items():
            visible = _project(geometry.difference(waters), forward)
            pieces = list(_parts(visible, {"LineString"}))
            if not pieces:
                continue
            combined = unary_union(pieces)
            merged = combined if combined.geom_type == "LineString" else linemerge(combined)
            continuous = list(_parts(merged, {"LineString"}))
            distance_px = max((part.length*scale for part in continuous), default=0)
            if distance_px >= len(name)*32+30:
                distances[name] = distance_px
        chosen_rivers = sorted(distances, key=distances.get, reverse=True)[:6]
    else:
        chosen_rivers = list(dict.fromkeys(str(n).strip() for n in river_names if str(n).strip()))
        missing = [n for n in chosen_rivers if n not in unions["rivers"]]
        if missing:
            raise DataServiceError("Requested rivers were not found in the current data or extent: " + ", ".join(missing) + ". Check the source names or adjust the extent.")
    def admin_level(name):
        return _admin_level(props_by_name[name])
    unknown_admin_levels = [name for name in admin_rank if not admin_level(name)]
    admin_names = [name for name in admin_names if admin_level(name)]
    selected = {
        "lake_labels": [{"name": n, "position": anchor_for(unions["lake"][n], n, 14, spaced=True), "font_size_pt": 14} for n in lake_names],
        "admin_labels": [{"name": n, "level": admin_level(n), "position": anchor_for(unions["admin"][n], n, {"province":19,"city":16.5,"county":15.5}[admin_level(n)], spaced=admin_level(n)!="county")} for n in admin_names],
        "river_labels": [{"source_name": n, "display_name": n, "anchor_near": None, "side": 1, "font_size_pt": 12} for n in chosen_rivers],
    }
    selection = {role: {"available_named_features": sorted(unions[role]),
                        "initial_selected_names": {"lake": lake_names, "admin": admin_names, "rivers": chosen_rivers}[role]}
                 for role in ROLES}
    selection["admin"]["names_without_declared_level"] = unknown_admin_levels
    return selected, selection


def _projection(bbox):
    w, s, e, n = bbox
    first = min(60, max(1, int(math.floor((w+180+1e-8)/6))+1))
    last = min(60, max(1, int(math.floor((e+180-1e-8)/6))+1))
    if first == last and e-w <= 6 and n-s <= 6 and not s < 0 < n:
        return "auto_utm"
    # Explicit local azimuthal equidistant projection avoids selecting a false UTM zone.
    return f"+proj=aeqd +lat_0={(s+n)/2:.8f} +lon_0={(w+e)/2:.8f} +datum=WGS84 +units=m +no_defs"


def _write_project(project_dir, params, layers, bbox, sources, provenance, supplied_job=None):
    project_dir = Path(project_dir)
    work = project_dir / "data_work"
    work.mkdir(parents=True, exist_ok=True)
    width, height = int(params.get("width_px") or 3840), int(params.get("height_px") or 2160)
    if not (1280 <= width <= 7680 and 720 <= height <= 4320) or abs(width/height-16/9) > 1e-6:
        raise DataServiceError("This edition supports a 16:9 aspect ratio, widths of 1280 to 7680 pixels, and heights of 720 to 4320 pixels.")
    job = {"schema_version": 1, "title": str(params.get("title") or "Rivers, Lakes, and Administrative Areas").strip(),
           "subtitle": "Cartographic working draft | Source records and quality reports included",
           "source_crs": "EPSG:4326", "render_crs": _projection(bbox), "extent_wgs84": bbox,
           "name_fields": {role: "name" for role in ROLES}, "source_records": {},
           "mask_rivers_by_lakes": True, "font_path": None,
           "output": {"width_px": width, "height_px": height, "dpi": width/16}}
    if len(job["title"]) > 65:
        raise DataServiceError("Limit the map title to 65 characters. Put detailed notes in the project documentation.")
    for role in ROLES:
        layer = layers.get(role)
        if layer and layer.get("features"):
            filename = work / (role + ".geojson")
            _save(filename, layer)
            job[role + "_file"] = "data_work/" + filename.name
            job["source_records"][role] = sources[role]
            provenance.setdefault("working_files", []).append({"role": role, "file": str(filename.relative_to(project_dir)),
                                                               "sha256": _sha(filename), "features": len(layer["features"])})
        else:
            job[role + "_file"] = None
            provenance.setdefault("warnings", []).append({"lake": "No usable lake polygons were obtained.", "rivers": "No usable river lines were obtained.", "admin": "No usable administrative polygons were obtained; the administrative layer is missing."}[role])
    if not any(job[r+"_file"] for r in ROLES):
        raise DataServiceError("No usable spatial features were obtained. Adjust the extent or import local GeoJSON.")
    suggestions, selection = _suggest_labels(layers, bbox, params.get("river_names"))
    job.update(suggestions)
    provenance["label_selection"] = selection
    provenance["label_selection_basis"] = "Initial labels are selected by visible area or length. Names and spatial relationships require manual review. Unlabelled features remain in the geometry layers."
    unknown = selection["admin"].get("names_without_declared_level", [])
    if unknown and not (supplied_job and supplied_job.get("admin_labels")):
        provenance.setdefault("warnings", []).append("Some administrative features have no declared province/city/county level. Their boundaries remain visible, but their levels were not inferred: " + ", ".join(unknown[:15]) + ". Supply properties.level or import a map configuration containing admin_labels.")
    if supplied_job:
        allowed_copy = ("title", "subtitle", "render_crs", "mask_rivers_by_lakes", "admin_labels", "river_labels", "lake_labels", "output")
        for key in allowed_copy:
            if key in supplied_job:
                job[key] = supplied_job[key]
        if params.get("title"):
            job["title"] = str(params["title"]).strip()
        # font_path is deliberately not copied: a foreign computer's absolute path is not portable.
    provenance["chosen_render_crs"] = job["render_crs"]
    provenance["extent_wgs84"] = bbox
    provenance["created_utc"] = _now()
    _save(project_dir / "data_provenance.json", provenance)
    _save(project_dir / "map_job.json", job)
    return project_dir / "map_job.json"


def build_import_project(project_dir, params, progress=None):
    project_dir = Path(project_dir)
    raw = project_dir / "data_raw"
    raw.mkdir(parents=True, exist_ok=True)
    _notify(progress, 8, "Checking imported layers and coordinate declarations")
    supplied_job = params.get("job") or {}
    if not isinstance(supplied_job, dict):
        raise DataServiceError("The map configuration job must be a JSON object.")
    permitted_job_fields = {"schema_version", "title", "subtitle", "extent_wgs84", "source_crs", "render_crs",
                            "lake_file", "rivers_file", "admin_file", "name_fields", "admin_labels", "river_labels",
                            "lake_labels", "source_records", "font_path", "output", "mask_rivers_by_lakes", "layers"}
    unknown_fields = set(supplied_job) - permitted_job_fields
    if unknown_fields:
        raise DataServiceError("Unsupported map configuration fields: " + ", ".join(sorted(unknown_fields)))
    if supplied_job.get("schema_version", 1) != 1:
        raise DataServiceError("Map configuration schema_version must be 1.")
    layers_input = params.get("layers") or supplied_job.get("layers") or {}
    if not isinstance(layers_input, dict) or not any(layers_input.get(role) for role in ROLES):
        raise DataServiceError("Import at least one lake, river, or administrative GeoJSON layer. A configuration file alone cannot access data paths on another computer.")
    source_crs = params.get("source_crs") or supplied_job.get("source_crs") or ("EPSG:4326" if params.get("confirm_wgs84") else None)
    try:
        crs_ok = source_crs and CRS.from_user_input(source_crs).equals(CRS.from_epsg(4326), ignore_axis_order=True)
    except Exception:
        crs_ok = False
    if not crs_ok:
        raise DataServiceError("Confirm that the imported data uses EPSG:4326 (longitude, latitude). Other coordinate systems require an actual transformation, not a changed label.")
    layers, sources, bounds = {}, {}, []
    provenance = {"mode": "local_import", "imported_utc": _now(),
                  "source_crs_declared": str(source_crs), "raw_files": [],
                  "warnings": ["Numeric coordinate checks cannot identify GCJ-02 or BD-09. EPSG:4326 is declared by the data provider."]}
    source_records = params.get("source_records") or supplied_job.get("source_records") or {}
    for role in ROLES:
        content = layers_input.get(role)
        if not content:
            layers[role] = {"type": "FeatureCollection", "features": []}
            continue
        _save(raw / (role + ".geojson"), content)
        layers[role] = _normalise_layer(content, role, (supplied_job.get("name_fields") or {}).get(role, "name"))
        if role == "admin" and params.get("admin_level"):
            declared = params["admin_level"]
            if declared not in ("province", "city", "county"):
                raise DataServiceError("A uniform administrative level must be province, city, or county. For mixed levels, declare properties.level on each feature.")
            for feature in layers[role]["features"]:
                if not feature["properties"].get("level") and not feature["properties"].get("admin_level"):
                    feature["properties"]["level"] = declared
        bounds += [shape(f["geometry"]).bounds for f in layers[role]["features"]]
        sources[role] = _source_record(role, source_records.get(role))
        provenance["raw_files"].append({"role": role, "file": f"data_raw/{role}.geojson", "sha256": _sha(raw / (role+".geojson"))})
    bbox = params.get("bbox") or supplied_job.get("extent_wgs84")
    if not bbox:
        bbox = _padded_bbox([min(b[0] for b in bounds), min(b[1] for b in bounds), max(b[2] for b in bounds), max(b[3] for b in bounds)])
    bbox = validate_bbox(bbox)
    _notify(progress, 30, "Local spatial data checked; creating the map configuration")
    return _write_project(project_dir, params, layers, bbox, sources, provenance, supplied_job)


def build_online_project(project_dir, params, progress=None):
    project_dir = Path(project_dir)
    raw, cache = project_dir / "data_raw", project_dir / "cache"
    raw.mkdir(parents=True, exist_ok=True)
    _notify(progress, 5, "Preparing a local online data query")
    bbox = params.get("bbox")
    if not bbox:
        raise DataServiceError("Search for and select a place, or enter an explicit map extent. The application does not choose between namesakes automatically.")
    bbox = validate_bbox(bbox, online=True)
    endpoint = _endpoint("overpass", params.get("endpoints"))
    w, s, e, n = bbox
    extent = f"({s:.7f},{w:.7f},{n:.7f},{e:.7f})"
    terms = [f'way["natural"="water"]["water"!~"^(river|canal)$"]{extent};',
             f'relation["natural"="water"]["water"!~"^(river|canal)$"]{extent};',
             f'way["landuse"="reservoir"]{extent};',
             f'way["waterway"~"^(river|canal)$"]{extent};',
             f'relation["boundary"="administrative"]["admin_level"="6"]{extent};']
    admin_requested = []
    admin_queries = params.get("admin_queries") or []
    if isinstance(admin_queries, str):
        admin_queries = [v.strip() for v in re.split(r"[\n;\uFF1B]+", admin_queries) if v.strip()]
    if len(admin_queries) > 8:
        raise DataServiceError("Specify at most 8 administrative areas per request. Reduce the extent or use local data.")
    _notify(progress, 12, "Checking requested administrative areas and the query extent")
    for user_query in admin_queries:
        results = search_places(user_query, cache, params.get("endpoints"))
        candidates = [r for r in results if r["osm_type"] == "relation" and r["osm_id"] is not None
                      and abs(_geod.inv((w+e)/2, (s+n)/2, r["lon"], r["lat"])[2]) < 250000]
        if not candidates:
            raise DataServiceError(f"No unambiguous administrative polygon was found for {user_query}. Include the full region name or import authoritative administrative GeoJSON.")
        # Require an unambiguous short name match, otherwise ask for a more precise query.
        short = re.split(r"[,\uFF0C]", str(user_query))[0].strip()
        exact = [r for r in candidates if r.get("short_name") == short]
        chosen = exact if exact else candidates
        if len(chosen) != 1:
            raise DataServiceError(f"Multiple administrative areas match {user_query}. Specify a more precise city or region and retry.")
        selected = chosen[0]
        osm_id = int(selected["osm_id"])
        terms.append(f'relation({osm_id})["boundary"="administrative"];')
        admin_requested.append({"query": str(user_query), "osm_id": osm_id, "name": selected["short_name"], "geocoder": selected})
    selected = params.get("selected_place") or {}
    if selected.get("osm_type") in ("way", "relation") and str(selected.get("osm_id", "")).isdigit():
        terms.append(f'{selected["osm_type"]}({int(selected["osm_id"])})["natural"="water"];')
    query = '[out:json][timeout:70][maxsize:67108864];(\n' + "\n".join(terms) + '\n);out meta geom;'
    (raw / "overpass_query.txt").write_text(query, encoding="utf-8")
    _notify(progress, 22, "Downloading water and administrative data; the public service may take about a minute")
    response, request_record = _request_json(endpoint, cache, urllib.parse.urlencode({"data": query}).encode(), timeout=90)
    _save(raw / "overpass_response.json", response)
    if len(response.get("elements", [])) > MAX_FEATURES:
        raise DataServiceError("Too many features were downloaded. Reduce the extent and retry. The original response is saved in the project.")
    _notify(progress, 38, "Preparing actual geometries, clipping the local extent, and recording sources")
    admin_scheme = params.get("admin_scheme") or selected.get("country_code") or "CN"
    layers, skipped = overpass_to_layers(response, bbox, admin_scheme=admin_scheme)
    found_admin_ids = {f["properties"].get("osm_id") for f in layers["admin"]["features"]}
    missing_admin = [r["query"] for r in admin_requested if r["osm_id"] not in found_admin_ids]
    if missing_admin:
        raise DataServiceError("Requested administrative areas have no complete valid polygon or lie outside the extent: " + ", ".join(missing_admin) + ". Adjust the extent or import local administrative data.")
    sources = {role: _source_record(role, online=True, retrieved=request_record["retrieved_utc"]) for role in ROLES}
    for record in sources.values():
        record["metadata_url"] = endpoint
        record["notes"] = "The complete query and raw response are saved in data_raw. Feature edit timestamps are not survey dates."
    provenance = {"mode": "online_openstreetmap_working_draft", "service_policies": NETWORK_POLICY_URLS,
                  "request": request_record, "raw_files": [{"file": "data_raw/overpass_response.json", "sha256": _sha(raw/"overpass_response.json")}],
                  "data_timestamp_osm_base": response.get("osm3s", {}).get("timestamp_osm_base"),
                  "requested_administrative_areas": admin_requested, "skipped_elements": skipped,
                  "administrative_level_mapping": {"scheme": admin_scheme, "CN": {"4":"province","5":"city","6":"county"}, "reference": NETWORK_POLICY_URLS["china_admin_levels"]},
                  "warnings": ["This working draft uses collaborative OpenStreetMap data. Verify administrative boundaries, names, and water coverage against authoritative sources.",
                               "The application does not infer lake inflow/outflow direction, extract DEM river networks, or detect water from remote sensing."]}
    if skipped:
        provenance["warnings"].append(f"{len(skipped)} online objects have incomplete or invalid geometry. See skipped_elements; no inferred lines were added.")
    job_path = _write_project(project_dir, params, layers, bbox, sources, provenance)
    focus_lake = None
    if selected.get("type") in ("lake", "water", "reservoir") and selected.get("osm_id") is not None:
        focus_lake = next((feature for feature in layers["lake"]["features"]
                           if str(feature["properties"].get("osm_id")) == str(selected["osm_id"]) and
                           feature["properties"].get("osm_type") == selected.get("osm_type")), None)
        if not focus_lake:
            raise DataServiceError("The selected lake has no complete valid water polygon. Inspect the raw response or import reliable lake data. This task cannot be marked as a completed lake map.")
    if admin_requested or focus_lake:
        job = json.loads(job_path.read_text(encoding="utf-8"))
        labels = {row["name"]: row for row in job["admin_labels"]}
        for row in admin_requested:
            actual = next(f for f in layers["admin"]["features"] if f["properties"].get("osm_id") == row["osm_id"])
            name = actual["properties"]["name"]
            if not name:
                raise DataServiceError(f"The requested administrative area {row['query']} has no verifiable source name.")
            level = _admin_level(actual["properties"])
            if level is None:
                raise DataServiceError(f"The source admin_level for {row['query']} has no supported province/city/county mapping. Verify the hierarchy and declare it in a local configuration.")
            labels[name] = {"name": name, "level": level, "position": None}
        job["admin_labels"] = list(labels.values())
        if focus_lake:
            focus_name = focus_lake["properties"].get("name")
            if not focus_name:
                raise DataServiceError("The selected lake has no source name. Verify it and provide a supported name through local data.")
            if focus_name not in {row["name"] for row in job["lake_labels"]}:
                job["lake_labels"].insert(0, {"name": focus_name, "position": None, "font_size_pt": 20})
        _save(job_path, job)
    _notify(progress, 48, "Data preparation complete; applying cartographic rules and rendering")
    return job_path


def read_project_summary(project_dir):
    project_dir = Path(project_dir)
    job = json.loads((project_dir/"map_job.json").read_text(encoding="utf-8"))
    provenance_file = project_dir / "data_provenance.json"
    provenance = json.loads(provenance_file.read_text(encoding="utf-8")) if provenance_file.exists() else {}
    return {"title": job["title"], "job": job, "features": provenance.get("label_selection", {}),
            "data_warnings": provenance.get("warnings", []), "source_records": job.get("source_records", {})}
