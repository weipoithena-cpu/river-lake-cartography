"""Place river names along a real visible line, without leader lines.

Latin names use intact words rotated along the local river tangent. Other
scripts retain the original upright-character placement mode.
"""
from __future__ import annotations

import math
import re
import numpy as np
import matplotlib.patheffects as pe
from matplotlib.font_manager import FontProperties
from matplotlib.transforms import Bbox
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import linemerge, unary_union


def line_parts(geometry):
    if geometry.is_empty:
        return
    if geometry.geom_type == "LineString":
        if geometry.length > 0:
            yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from line_parts(part)


def continuous_lines(geometry):
    parts = list(line_parts(geometry))
    if not parts:
        return []
    union = unary_union(parts)
    merged = union if union.geom_type == "LineString" else linemerge(union)
    return list(line_parts(merged))


def text_footprint(artist, renderer):
    """Measure the rotated text rectangle, rather than its enclosing AABB.

    Adjacent words on a diagonal baseline can have overlapping axis-aligned
    bounds despite disjoint text rectangles. Respect rotation when checking
    these collisions; use the actual unrotated Matplotlib text extent.
    """
    angle = float(artist.get_rotation())
    try:
        artist.set_rotation(0)
        bounds = artist.get_window_extent(renderer)
    finally:
        artist.set_rotation(angle)
    corners = np.array([[bounds.x0, bounds.y0], [bounds.x1, bounds.y0],
                        [bounds.x1, bounds.y1], [bounds.x0, bounds.y1]])
    if angle:
        anchor = artist.get_transform().transform(artist.get_position())
        theta = math.radians(angle)
        rotation = np.array([[math.cos(theta), -math.sin(theta)],
                             [math.sin(theta), math.cos(theta)]])
        corners = (corners - anchor) @ rotation.T + anchor
    return Polygon(corners)


def draw_river_label(ax, geometry, near_xy, text, font, *, size=12.0,
                     gap_pt=2.0, offset_pt=7.0, side=1,
                     obstacles=(), color="#347F9F"):
    """Return artists and measured placement; an unplaced label is explicit.

    geometry/near_xy use projected map coordinates. Finalize axes limits/aspect
    before this call. Character positions follow the real continuous geometry;
    the glyphs stay upright. Horizontal names read left to right, vertical names
    top to bottom. Text orientation is not a statement of river flow direction.
    """
    if re.search(r"[A-Za-z]", text):
        return draw_latin_river_label(
            ax, geometry, near_xy, text, font, size=size, gap_pt=gap_pt,
            offset_pt=offset_pt, side=side, obstacles=obstacles, color=color)
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    px_per_pt = fig.dpi / 72.0
    fp = FontProperties(fname=font.get_file(), size=size)
    widths = np.array([renderer.get_text_width_height_descent(c, fp, False)[0]
                       for c in text], dtype=float)
    height = size * px_per_pt * 1.20
    # Diagonal-sized cells prevent upright glyphs touching on diagonal rivers.
    cells = np.hypot(widths + 2.0, height + 2.0)
    gap = gap_pt * px_per_pt
    total = float(cells.sum() + gap * max(0, len(text) - 1))
    offsets = np.cumsum(cells) - cells / 2 + gap * np.arange(len(text)) - total / 2
    near_pixels = np.asarray(ax.transData.transform(near_xy))
    near_point = Point(*near_pixels)
    frame = ax.get_window_extent(renderer)
    candidates = []
    parts = continuous_lines(geometry)

    for line_index, part in enumerate(parts):
        array = ax.transData.transform(np.asarray(part.coords))
        screen = LineString(array)
        if screen.length < total + 6 * px_per_pt:
            continue
        center = screen.project(near_point)
        margin = total / 2 + 2 * px_per_pt
        for shift in (0, -.6 * total, .6 * total, -total, total, -2 * total, 2 * total):
            distance = float(np.clip(center + shift, margin, screen.length - margin))
            start = np.asarray(screen.interpolate(distance - total / 2).coords[0])
            end = np.asarray(screen.interpolate(distance + total / 2).coords[0])
            delta = end - start
            if np.linalg.norm(delta) < 1:
                continue
            vertical = abs(delta[1]) > abs(delta[0])
            reverse = (vertical and delta[1] > 0) or (not vertical and delta[0] < 0)
            path = LineString(array[::-1]) if reverse else screen
            at_center = path.length - distance if reverse else distance
            for candidate_side in (side, -side):
                poses, boxes, anchors = [], [], []
                for char, width, offset in zip(text, widths, offsets):
                    at = at_center + offset
                    anchor = np.asarray(path.interpolate(at).coords[0])
                    before = np.asarray(path.interpolate(max(0, at - 5 * px_per_pt)).coords[0])
                    after = np.asarray(path.interpolate(min(path.length, at + 5 * px_per_pt)).coords[0])
                    tangent = after - before
                    norm = np.linalg.norm(tangent)
                    if norm == 0:
                        break
                    tangent /= norm
                    normal = np.array([-tangent[1], tangent[0]])
                    pos = anchor + candidate_side * offset_pt * px_per_pt * normal
                    boxes.append(Bbox.from_bounds(pos[0] - width / 2 - 1,
                                                 pos[1] - height / 2 - 1,
                                                 width + 2, height + 2))
                    poses.append((char, pos))
                    anchors.append(anchor)
                if len(poses) != len(text):
                    continue
                pos_array = np.array([p for _, p in poses])
                movement = np.diff(pos_array[:, 1 if vertical else 0])
                monotone = bool(np.all(movement < -.1) if vertical
                                else np.all(movement > .1))
                if not monotone:
                    continue
                outside = any(not frame.contains(b.x0, b.y0) or
                              not frame.contains(b.x1, b.y1) for b in boxes)
                collision = any(b.overlaps(o) for b in boxes for o in obstacles)
                self_collision = any(boxes[i].overlaps(boxes[j])
                                     for i in range(len(boxes))
                                     for j in range(i + 1, len(boxes)))
                if outside or collision or self_collision:
                    continue
                mid = np.asarray(path.interpolate(at_center).coords[0])
                score = float(np.linalg.norm(mid - near_pixels))
                score += 1.5 if candidate_side != side else 0
                candidates.append((score, line_index, poses, anchors, vertical,
                                   candidate_side, movement.tolist()))

    if not candidates:
        return [], {
            "name": text, "status": "unplaced",
            "reason": "No sufficiently long visible river segment satisfies reading order, map-frame, and collision rules",
            "continuous_segments_examined": len(parts), "leader_line_count": 0,
        }
    _, line_index, poses, anchors, vertical, chosen_side, movement = min(
        candidates, key=lambda item: item[0])
    artists = []
    for char, position in poses:
        data = ax.transData.inverted().transform(position)
        artists.append(ax.text(*data, char, fontproperties=fp, fontsize=size,
                               color=color, ha="center", va="center", rotation=0,
                               zorder=12, path_effects=[
                                   pe.withStroke(linewidth=1.6, foreground="white")]))
    source_anchors = [ax.transData.inverted().transform(point).tolist() for point in anchors]
    positions = [ax.transData.inverted().transform(point).tolist() for _, point in poses]
    return artists, {
        "name": text, "status": "placed", "continuous_line_index": line_index,
        "layout": "upright_characters_along_visible_river",
        "reading_order": "top_to_bottom" if vertical else "left_to_right",
        "reading_axis_steps_pixels": movement,
        "reading_order_measured_monotone": bool(all(v < -.1 for v in movement)
                                               if vertical else all(v > .1 for v in movement)),
        "leader_line_count": sum(getattr(a, "arrow_patch", None) is not None for a in artists),
        "font_size_pt": size, "gap_pt": gap_pt, "offset_pt": offset_pt, "side": chosen_side,
        "source_anchor_projected_xy": source_anchors,
        "letter_positions_projected_xy": positions,
        "source_anchor_max_distance_projected": float(max(
            geometry.distance(Point(*point)) for point in source_anchors)),
    }


def draw_latin_river_label(ax, geometry, near_xy, text, font, *, size=12.0,
                          gap_pt=2.0, offset_pt=7.0, side=1,
                          obstacles=(), color="#347F9F"):
    """Keep Latin words readable while following a measured visible river.

    Each word is aligned with its own local chord. Sharply curved word spans,
    inverted text, nonmonotone word order, overlaps, and frame crossings are
    rejected. Requested names are never abbreviated or silently dropped.
    """
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    px_per_pt = fig.dpi / 72.0
    fp = FontProperties(fname=font.get_file(), size=size)
    words = text.split()
    widths = np.array([renderer.get_text_width_height_descent(w, fp, False)[0]
                       for w in words], dtype=float)
    height = size * px_per_pt * 1.20
    gap = (renderer.get_text_width_height_descent(" ", fp, False)[0]
           + gap_pt * px_per_pt)
    total = float(widths.sum() + gap * max(0, len(words) - 1))
    offsets = np.cumsum(widths) - widths / 2 + gap * np.arange(len(words)) - total / 2
    near_pixels = np.asarray(ax.transData.transform(near_xy))
    frame = ax.get_window_extent(renderer)
    candidates = []
    parts = continuous_lines(geometry)
    for line_index, part in enumerate(parts):
        coordinates = ax.transData.transform(np.asarray(part.coords))
        screen = LineString(coordinates)
        margin = total / 2 + 3 * px_per_pt
        if screen.length <= 2 * margin:
            continue
        preferred = screen.project(Point(*near_pixels))
        distances = [float(np.clip(preferred + f * total, margin, screen.length - margin))
                     for f in (0, -.3, .3, -.6, .6, -1, 1, -2, 2)]
        distances.extend(np.linspace(margin, screen.length - margin, 17))
        for distance in dict.fromkeys(distances):
            start = np.asarray(screen.interpolate(distance - total / 2).coords[0])
            end = np.asarray(screen.interpolate(distance + total / 2).coords[0])
            delta = end - start
            if np.linalg.norm(delta) < total * .75:
                continue
            reverse = delta[0] < 0 or (abs(delta[0]) < .01 and delta[1] > 0)
            path = LineString(coordinates[::-1]) if reverse else screen
            center = path.length - distance if reverse else distance
            direction = -delta if reverse else delta
            vertical = abs(direction[1]) > abs(direction[0])
            reading_sign = np.sign(direction[1] if vertical else direction[0])
            for candidate_side in (side, -side):
                poses, anchors, boxes, footprints = [], [], [], []
                for word, width, offset in zip(words, widths, offsets):
                    at = center + offset
                    anchor = np.asarray(path.interpolate(at).coords[0])
                    before = np.asarray(path.interpolate(at - width / 2).coords[0])
                    after = np.asarray(path.interpolate(at + width / 2).coords[0])
                    tangent = after - before
                    chord = np.linalg.norm(tangent)
                    if chord < width * .94:
                        break
                    angle = math.degrees(math.atan2(tangent[1], tangent[0]))
                    if not -90 <= angle <= 90:
                        break
                    tangent /= chord
                    normal = np.array([-tangent[1], tangent[0]])
                    position = anchor + candidate_side * offset_pt * px_per_pt * normal
                    # Conservative rotated axis-aligned bounds, later checked
                    # again against actual Matplotlib artist extents.
                    cosine, sine = abs(tangent[0]), abs(tangent[1])
                    box_width = width * cosine + height * sine + 4
                    box_height = width * sine + height * cosine + 4
                    bounds = Bbox.from_bounds(position[0] - box_width / 2,
                                              position[1] - box_height / 2,
                                              box_width, box_height)
                    boxes.append(bounds)
                    half_w, half_h = width / 2 + 1, height / 2 + 1
                    local_corners = np.array([[-half_w, -half_h], [half_w, -half_h],
                                              [half_w, half_h], [-half_w, half_h]])
                    rotation = np.array([[tangent[0], -tangent[1]],
                                         [tangent[1], tangent[0]]])
                    footprints.append(Polygon(local_corners @ rotation.T + position))
                    poses.append((word, position, angle))
                    anchors.append(anchor)
                if len(poses) != len(words):
                    continue
                movements = np.diff(np.array([p[1] for p in poses])[:, int(vertical)])
                if not np.all(movements * reading_sign > .1):
                    continue
                if any(not frame.contains(b.x0, b.y0) or not frame.contains(b.x1, b.y1)
                       for b in boxes):
                    continue
                if any(b.overlaps(o) for b in boxes for o in obstacles):
                    continue
                if any(a.intersection(b).area > 1e-6
                       for i, a in enumerate(footprints) for b in footprints[i + 1:]):
                    continue
                midpoint = np.asarray(path.interpolate(center).coords[0])
                score = float(np.linalg.norm(midpoint - near_pixels))
                score += 1.5 if candidate_side != side else 0
                candidates.append((score, line_index, poses, anchors,
                                   candidate_side, movements.tolist(), vertical, reading_sign))
    if not candidates:
        return [], {"name": text, "status": "unplaced",
                    "reason": "No visible river span fits the full Latin name with readable word orientation and collision-free placement",
                    "continuous_segments_examined": len(parts), "leader_line_count": 0}
    _, line_index, poses, anchors, chosen_side, movements, vertical, direction = min(
        candidates, key=lambda item: item[0])
    artists = []
    for word, position, angle in poses:
        point = ax.transData.inverted().transform(position)
        artists.append(ax.text(*point, word, fontproperties=fp, fontsize=size,
                               color=color, ha="center", va="center", rotation=angle,
                               rotation_mode="anchor", zorder=12,
                               path_effects=[pe.withStroke(linewidth=1.6, foreground="white")]))
    source_anchors = [ax.transData.inverted().transform(p).tolist() for p in anchors]
    positions = [ax.transData.inverted().transform(p).tolist() for _, p, _ in poses]
    return artists, {
        "name": text, "status": "placed", "continuous_line_index": line_index,
        "layout": "latin_words_along_visible_river", "word_count": len(words),
        "reading_order": (("bottom_to_top" if direction > 0 else "top_to_bottom")
                          if vertical else "left_to_right"),
        "reading_axis_steps_pixels": movements,
        "reading_order_measured_monotone": bool(all(v * direction > .1 for v in movements)),
        "word_rotations_degrees": [float(angle) for _, _, angle in poses],
        "leader_line_count": 0,
        "font_size_pt": size, "gap_pt": gap_pt, "offset_pt": offset_pt, "side": chosen_side,
        "source_anchor_projected_xy": source_anchors,
        "letter_positions_projected_xy": positions,
        "source_anchor_max_distance_projected": float(max(
            geometry.distance(Point(*point)) for point in source_anchors)),
    }
