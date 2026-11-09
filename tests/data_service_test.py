"""Focused checks for coordinate, geometry and provenance failures."""
import json
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from data_service import (DataServiceError, build_import_project, overpass_to_layers,
                          validate_bbox, _suggest_labels, _admin_level)
from shapely.geometry import shape


def collection(geometry, properties=None):
    return {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": properties or {}, "geometry": geometry}]}


POLYGON = {"type": "Polygon", "coordinates": [[[118,31],[118.2,31],[118.2,31.2],[118,31.2],[118,31]]]}


class PreparationTests(unittest.TestCase):
    def test_declared_crs_is_required(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(DataServiceError, "Confirm that the imported data"):
                build_import_project(temp, {"layers": {"lake": collection(POLYGON)}})

    def test_projected_numbers_are_rejected_not_relabelled(self):
        projected = {"type": "Polygon", "coordinates": [[[500000,4000000],[501000,4000000],[501000,4001000],[500000,4000000]]]}
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(DataServiceError, "longitude/latitude"):
                build_import_project(temp, {"source_crs": "EPSG:4326", "layers": {"lake": collection(projected)}})

    def test_large_online_scope_is_rejected(self):
        with self.assertRaisesRegex(DataServiceError, "Online drafts are limited to local extents"):
            validate_bbox([116,30,120,33], online=True)

    def test_configuration_cannot_load_arbitrary_local_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(DataServiceError, "Import at least one"):
                build_import_project(temp, {"job": {"source_crs": "EPSG:4326", "lake_file": "C:/private/file.json"}})

    def test_unknown_admin_level_is_not_invented(self):
        layers = {"admin": collection(POLYGON, {"name": "Sample Administrative Area"}),
                  "lake": {"features": []}, "rivers": {"features": []}}
        labels, selection = _suggest_labels(layers, [117.9,30.9,118.3,31.3])
        self.assertEqual(labels["admin_labels"], [])
        self.assertIn("Sample Administrative Area", selection["admin"]["names_without_declared_level"])

    def test_china_osm_hierarchy_is_not_generic_4_6_8(self):
        self.assertEqual(_admin_level({"cartography_admin_scheme":"CN", "admin_level":"4"}), "province")
        self.assertEqual(_admin_level({"cartography_admin_scheme":"CN", "admin_level":"5"}), "city")
        self.assertEqual(_admin_level({"cartography_admin_scheme":"CN", "admin_level":"6"}), "county")
        self.assertIsNone(_admin_level({"cartography_admin_scheme":"CN", "admin_level":"8"}))
        self.assertIsNone(_admin_level({"admin_level":"6"}))

    def test_missing_mandatory_river_is_reported(self):
        layers = {role: {"features": []} for role in ("lake", "rivers", "admin")}
        with self.assertRaisesRegex(DataServiceError, "Requested rivers"):
            _suggest_labels(layers, [118,31,118.2,31.2], ["Required River"])

    def test_multipolygon_hole_is_retained(self):
        def coords(points):
            return [{"lon": x, "lat": y} for x,y in points]
        relation = {"type": "relation", "id": 1, "tags": {"natural": "water", "name": "Test Lake"}, "members": [
            {"type": "way", "ref": 1, "role": "outer", "geometry": coords([(118,31),(118.2,31),(118.2,31.2)])},
            {"type": "way", "ref": 2, "role": "outer", "geometry": coords([(118.2,31.2),(118,31.2),(118,31)])},
            {"type": "way", "ref": 3, "role": "inner", "geometry": coords([(118.05,31.05),(118.1,31.05),(118.1,31.1),(118.05,31.1),(118.05,31.05)])}]}
        layers, skipped = overpass_to_layers({"elements": [relation]}, [117.9,30.9,118.3,31.3])
        self.assertFalse(skipped)
        geometry = shape(layers["lake"]["features"][0]["geometry"])
        self.assertEqual(len(geometry.interiors), 1)
        self.assertAlmostEqual(geometry.area, .04-.0025)

    def test_incomplete_boundary_is_not_closed_by_guessing(self):
        relation = {"type": "relation", "id": 2, "tags": {"boundary": "administrative", "name": "Test County", "admin_level": "8"},
                    "members": [{"type": "way", "ref": 1, "role": "outer", "geometry": [
                        {"lon":118,"lat":31},{"lon":118.2,"lat":31},{"lon":118.2,"lat":31.2}]}]}
        layers, skipped = overpass_to_layers({"elements": [relation]}, [117.9,30.9,118.3,31.3])
        self.assertFalse(layers["admin"]["features"])
        self.assertEqual(len(skipped), 1)

    def test_import_writes_traceable_portable_project(self):
        with tempfile.TemporaryDirectory() as temp:
            job_file = build_import_project(temp, {"title":"Test Import", "source_crs":"EPSG:4326",
                     "layers":{"lake":collection(POLYGON,{"name":"Test Lake"})}})
            job = json.loads(job_file.read_text(encoding="utf-8"))
            self.assertEqual(job["source_crs"], "EPSG:4326")
            self.assertEqual(job["lake_file"], "data_work/lake.geojson")
            self.assertTrue((Path(temp)/"data_provenance.json").exists())
            self.assertEqual(job["source_records"]["lake"]["year"], "Not specified")
            self.assertNotIn("retrieved_utc", job["source_records"]["lake"],
                             "An import must not invent the original source retrieval date")
            provenance = json.loads((Path(temp)/"data_provenance.json").read_text())
            self.assertIsNotNone(datetime.fromisoformat(provenance["imported_utc"]).tzinfo)


if __name__ == "__main__":
    unittest.main(verbosity=2)
