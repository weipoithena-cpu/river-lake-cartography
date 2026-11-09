"""Real local HTTP + actual map rendering integration checks (no public network)."""
from pathlib import Path
import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import io

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from main import App, Handler, ThreadingHTTPServer


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="river-lake-test-")
        cls.app = App(Path(cls.temp.name))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.server.app = cls.app
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = "http://127.0.0.1:" + str(cls.server.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.app.executor.shutdown(wait=True)
        cls.temp.cleanup()

    def request(self, path, payload=None, token=True, extra=None):
        headers = {"X-App-Token": self.app.token} if token else {}
        headers.update(extra or {})
        data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.url + urllib.parse.quote(path, safe="/"), data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            result = response.read()
            return json.loads(result) if response.headers.get_content_type() == "application/json" else result

    def wait_task(self, task_id):
        until = time.monotonic() + 80
        while time.monotonic() < until:
            task = self.request("/api/task/" + task_id)
            if task["status"] not in ("queued", "running"):
                return task
            time.sleep(.15)
        self.fail("map task exceeded 80 seconds")

    def test_01_environment_and_page(self):
        status = self.request("/api/status")
        self.assertEqual(status["environment"]["status"], "ready")
        self.assertFalse(status["capabilities"]["ai_agent_embedded"])
        page = self.request("/", token=False)
        self.assertIn(self.app.token.encode(), page)
        self.assertNotIn(b"__APP_TOKEN__", page)

    def test_02_auth_origin_and_traversal(self):
        for path, token, extra in [("/api/status", False, {}),
                                    ("/api/status", True, {"Origin": "https://example.org"}),
                                    ("/api/status", True, {"Host": "evil.example"})]:
            with self.assertRaises(urllib.error.HTTPError) as context:
                self.request(path, token=token, extra=extra)
            self.assertEqual(context.exception.code, 403)

    def test_03_real_example_and_portable_export(self):
        task = self.wait_task(self.request("/api/example", {"id": "shijiu"})["task_id"])
        self.assertIn(task["status"], ("completed", "completed_with_warnings"),
                      task.get("error") or task.get("message"))
        result = task["result"]
        self.assertEqual(result["qa"]["errors"], [])
        self.assertEqual(result["qa"]["label_counts"]["placed_admin"], 8)
        self.assertEqual(result["qa"]["label_counts"]["placed_rivers"], 5)
        png = self.request(result["preview_url"])
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        export = next(x for x in result["downloads"] if x["filename"] == "project_export.zip")
        with zipfile.ZipFile(io.BytesIO(self.request(export["url"]))) as archive:
            job = json.loads(archive.read("map_job.json"))
            self.assertIsNone(job["font_path"])
            self.assertIn("data_work/shijiu_lake_osm.geojson", archive.namelist())
        with self.assertRaises(urllib.error.HTTPError) as context:
            self.request(f"/api/artifact/{result['project_id']}/../../outside.txt")
        self.assertEqual(context.exception.code, 404)
        # A failed new version must preserve and expose its diagnostic PNG.
        bad_job = dict(result["job"])
        bad_job["river_labels"] = [{"source_name": "Nonexistent Test River"}]
        failed = self.wait_task(self.request("/api/rerender", {"project_id": result["project_id"], "job": bad_job})["task_id"])
        self.assertEqual(failed["status"], "failed")
        self.assertTrue(failed["result"]["preview_url"].endswith("diagnostic_preview.png"))
        self.assertNotEqual(failed["result"]["project_id"], result["project_id"])
        previous = self.request("/api/projects/" + result["project_id"])
        self.assertEqual(previous["qa"]["errors"], [])

    def test_04_import_requires_coordinate_declaration(self):
        layer = json.loads((ROOT / "app/examples/shijiu/data_work/shijiu_lake_osm.geojson").read_text())
        task = self.wait_task(self.request("/api/import", {"title": "Import Validation", "layers": {"lake": layer}})["task_id"])
        self.assertEqual(task["status"], "failed")
        self.assertIn("4326", task["error"])

    def test_05_real_geojson_import(self):
        example = ROOT / "app/examples/shijiu"
        job = json.loads((example / "map_job.json").read_text())
        layers = {role: json.loads((example / job[role + "_file"]).read_text()) for role in ("lake", "rivers", "admin")}
        task = self.wait_task(self.request("/api/import", {"title": "Imported Data Validation", "source_crs": "EPSG:4326", "job": job, "layers": layers, "source_records": job["source_records"]})["task_id"])
        self.assertIn(task["status"], ("completed", "completed_with_warnings"),
                      task.get("error") or task.get("message"))
        self.assertEqual(task["result"]["qa"]["label_counts"]["placed_rivers"], 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
