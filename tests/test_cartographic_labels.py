"""Measured typography regressions using real Matplotlib artists and geometry.

These tests check placement properties, not whether a map's source data or
geographic names are authoritative. They require no network or browser.
"""
from pathlib import Path
import sys
import unittest

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.font_manager import FontProperties
from shapely.geometry import LineString, Point

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "core"))
from cartographic_labels import draw_river_label, text_footprint


class RiverTypographyTests(unittest.TestCase):
    def setUp(self):
        self.figure, self.axes = plt.subplots(figsize=(9, 5), dpi=100)
        self.axes.set_xlim(0, 1000)
        self.axes.set_ylim(0, 500)
        self.axes.set_aspect("equal", adjustable="box")
        self.font = FontProperties(
            fname=str(ROOT / "app/resources/fonts/NotoSansCJK-Regular.ttc"))
        self.figure.canvas.draw()

    def tearDown(self):
        plt.close(self.figure)

    def assert_valid_latin_placement(self, line, artists, record, name):
        self.assertEqual(record["status"], "placed", record)
        # Every word must survive intact, in its original sequence.
        self.assertEqual([artist.get_text() for artist in artists], name.split())
        self.assertEqual(" ".join(artist.get_text() for artist in artists), name)
        self.assertTrue(record["reading_order_measured_monotone"])
        self.assertEqual(record["leader_line_count"], 0)
        self.assertTrue(all(getattr(artist, "arrow_patch", None) is None
                            for artist in artists))
        self.assertFalse(self.axes.patches, "River labels must not add leader arrows")
        for angle in record["word_rotations_degrees"]:
            self.assertGreaterEqual(angle, -90)
            self.assertLessEqual(angle, 90)
        # Label text can be offset from the channel; its measured source anchors
        # must lie on the actual river geometry instead of an invented baseline.
        for anchor in record["source_anchor_projected_xy"]:
            self.assertLess(line.distance(Point(*anchor)), 1e-8)
        self.assertLess(record["source_anchor_max_distance_projected"], 1e-8)
        self.figure.canvas.draw()
        renderer = self.figure.canvas.get_renderer()
        frame = self.axes.get_window_extent(renderer)
        boxes = [artist.get_window_extent(renderer) for artist in artists]
        for bounds in boxes:
            self.assertTrue(frame.contains(bounds.x0, bounds.y0))
            self.assertTrue(frame.contains(bounds.x1, bounds.y1))
        footprints = [text_footprint(artist, renderer) for artist in artists]
        for index, footprint in enumerate(footprints):
            for other in footprints[index + 1:]:
                self.assertLess(footprint.intersection(other).area, 1e-8,
                                "The rotated word rectangles must not overlap")

    def test_latin_words_remain_intact_on_a_curved_river(self):
        line = LineString([(80, 180), (300, 205), (550, 245), (920, 285)])
        name = "Silver-Pine River"
        artists, record = draw_river_label(
            self.axes, line, (500, 240), name, self.font)
        self.assert_valid_latin_placement(line, artists, record, name)
        self.assertTrue(any(abs(angle) > 2 for angle in record["word_rotations_degrees"]),
                        "Words should follow the sloped river, not a horizontal replacement")

    def test_reversed_source_geometry_does_not_reverse_reading_order(self):
        line = LineString([(930, 260), (70, 260)])
        artists, record = draw_river_label(
            self.axes, line, (500, 260), "Long Meadow River", self.font)
        self.assert_valid_latin_placement(line, artists, record, "Long Meadow River")
        anchors = record["source_anchor_projected_xy"]
        self.assertTrue(all(a[0] < b[0] for a, b in zip(anchors, anchors[1:])))
        self.assertEqual(record["reading_order"], "left_to_right")

    def test_vertical_river_uses_readable_monotone_word_order(self):
        line = LineString([(500, 35), (500, 465)])
        artists, record = draw_river_label(
            self.axes, line, (500, 250), "Willow River", self.font)
        self.assert_valid_latin_placement(line, artists, record, "Willow River")
        anchors = record["source_anchor_projected_xy"]
        self.assertTrue(all(a[1] > b[1] for a, b in zip(anchors, anchors[1:])))
        self.assertEqual(record["reading_order"], "top_to_bottom")

    def test_diagonal_footprints_distinguish_false_and_actual_overlap(self):
        line = LineString([(280, 30), (720, 470)])
        artists, record = draw_river_label(
            self.axes, line, (500, 250), "Silver River", self.font)
        self.assert_valid_latin_placement(line, artists, record, "Silver River")
        renderer = self.figure.canvas.get_renderer()
        first, second = artists
        self.assertAlmostEqual(record["word_rotations_degrees"][0], 45, places=7)
        self.assertTrue(first.get_window_extent(renderer).overlaps(
            second.get_window_extent(renderer)),
            "The fixture must reproduce overlapping axis-aligned bounds")
        self.assertLess(text_footprint(first, renderer).intersection(
            text_footprint(second, renderer)).area, 1e-8)
        # A true overlap at the same anchor must still be caught. A blanket
        # exception for words in the same river name would miss this case.
        second.set_position(first.get_position())
        self.figure.canvas.draw()
        self.assertGreater(text_footprint(first, renderer).intersection(
            text_footprint(second, renderer)).area, 1)
        self.assertAlmostEqual(first.get_rotation(), 45, places=7)
        self.assertAlmostEqual(second.get_rotation(), 45, places=7)

    def test_short_span_reports_the_full_name_as_unplaced(self):
        name = "Long Meadow Tributary"
        line = LineString([(490, 250), (510, 250)])
        artists, record = draw_river_label(
            self.axes, line, (500, 250), name, self.font)
        self.assertEqual(artists, [])
        self.assertEqual(record["status"], "unplaced")
        self.assertEqual(record["name"], name)
        self.assertTrue(record["reason"])
        self.assertEqual(record["leader_line_count"], 0)
        self.assertFalse(self.axes.texts, "Rejected names must not leave a partial label")

    def test_blocked_span_is_not_drawn_over_an_obstacle(self):
        line = LineString([(70, 250), (930, 250)])
        obstacle = self.axes.get_window_extent(self.figure.canvas.get_renderer())
        artists, record = draw_river_label(
            self.axes, line, (500, 250), "Silver River", self.font,
            obstacles=[obstacle])
        self.assertEqual(artists, [])
        self.assertEqual(record["status"], "unplaced")
        self.assertFalse(self.axes.texts)

    def test_existing_non_latin_character_mode_is_preserved(self):
        # The fixture is encoded to keep this published test file English-only.
        name = "\u6e05\u6cb3"
        line = LineString([(70, 250), (930, 250)])
        artists, record = draw_river_label(
            self.axes, line, (500, 250), name, self.font)
        self.assertEqual(record["status"], "placed", record)
        self.assertEqual("".join(artist.get_text() for artist in artists), name)
        self.assertTrue(all(artist.get_rotation() == 0 for artist in artists))
        self.assertTrue(record["reading_order_measured_monotone"])
        self.assertEqual(record["leader_line_count"], 0)
        for anchor in record["source_anchor_projected_xy"]:
            self.assertLess(line.distance(Point(*anchor)), 1e-8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
