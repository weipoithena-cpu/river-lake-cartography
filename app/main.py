"""River Lake Cartography: a local-only desktop web application.

The Windows launcher runs this file with its bundled Python. The server binds
only to 127.0.0.1; imported spatial data is processed on this computer.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import shutil
import sys
import tempfile
import threading
import time
import traceback
from urllib.parse import unquote, urlsplit
import uuid
import webbrowser
import zipfile

APP_DIR = Path(__file__).resolve().parent
CORE_DIR = APP_DIR / "core"
sys.path.insert(0, str(CORE_DIR))
sys.path.insert(0, str(APP_DIR))
VERSION = "1.0.0-preview.1"
FONT = APP_DIR / "resources" / "fonts" / "NotoSansCJK-Regular.ttc"
MAX_BODY = 48 * 1024 * 1024


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def documents_dir():
    if os.name == "nt":
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(32768)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:
                return Path(buf.value)
        except Exception:
            pass
    return Path.home() / "Documents"


def environment_report():
    from check_environment import collect_environment
    return collect_environment(str(FONT) if FONT.is_file() else None)


def render_project(project_dir: Path, progress=None):
    """Use the same measured cartographic gates as the skill, without a subprocess."""
    import render_map
    from matplotlib import pyplot as plt
    from importlib.metadata import version

    job_path = project_dir / "map_job.json"
    job = read_json(job_path)
    if FONT.is_file():
        # A bundled freely redistributable font gives consistent label metrics.
        job["font_path"] = str(FONT)
    atomic_json(job_path, job)
    output = project_dir / "output"
    output.mkdir(exist_ok=True)
    qa = {
        "schema_version": 1,
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"),
        "created_utc": utc_now(), "job_file": str(job_path),
        "renderer_sha256": render_map.file_hash(CORE_DIR / "render_map.py"),
        "support_script_sha256": {name: render_map.file_hash(CORE_DIR / name)
                                  for name in ("check_environment.py", "cartographic_labels.py")},
        "source_records_authority": "supplied_by_job_not_certified_by_renderer",
        "status": "running", "layers": {}, "errors": [], "warnings": [], "outputs": [],
        "versions": {"python": sys.version.split()[0],
                     **{name: version(name) for name in ("numpy", "matplotlib", "shapely", "pyproj")}},
        "manual_visual_review": {"status": "pending", "note": "Review the actual PNG. The application does not automatically mark manual visual review as passed."},
    }
    try:
        if progress:
            progress(72, "Projecting data, placing river labels, and checking administrative labels and the legend")
        render_map.render(job_path, output, qa)
    except Exception as exc:
        qa["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        plt.close("all")
    provenance = project_dir / "data_provenance.json"
    if provenance.exists():
        data = read_json(provenance)
        for warning in data.get("warnings", []):
            warning = str(warning)
            if warning not in qa["warnings"]:
                qa["warnings"].append(warning)
    qa["missing_or_unplaced_labels"] = [
        {"kind": kind, **record}
        for kind, key in (("admin", "admin_labels"), ("river", "river_labels"), ("lake", "lake_labels"))
        for record in qa.get(key, []) if record.get("status") != "placed"
    ]
    qa["status"] = "failed" if qa["errors"] else "completed_with_warnings" if qa["warnings"] else "completed"
    atomic_json(output / "qa.json", qa)
    write_review(project_dir, qa)
    # The portable configuration uses a relative font reference only if available.
    # On another computer the renderer can choose its own valid Chinese font.
    portable = dict(job)
    portable["font_path"] = None
    atomic_json(project_dir / "map_job.portable.json", portable)
    if progress:
        progress(96, "Saved images, sources, and quality reports")
    return qa


def write_review(project_dir: Path, qa):
    checks = qa.get("layout_checks", {})
    counts = qa.get("label_counts", {})
    river_count = counts.get("requested_rivers", 0)
    admin_count = counts.get("requested_admin", 0)
    def flag(value):
        return "Passed" if value else "Failed"
    lines = ["# Map Quality Report", "", f"Generated: {qa['created_utc']}", "",
             f"Automated check status: {qa['status']}", "", "| Check | Result |", "|---|---|",
             f"| Legend inside lower-left map frame | {flag(checks.get('legend_inside_map') and checks.get('legend_lower_left'))} |",
             f"| River labels follow rivers without leader lines | {'Not applicable' if not river_count else flag(counts.get('placed_rivers') == river_count and checks.get('river_leader_line_count') == 0)} |",
             f"| Complete administrative labels inside their regions | {'Not applicable' if not admin_count else flag(counts.get('placed_admin') == admin_count and all(x.get('whole_text_inside_visible_area') for x in checks.get('admin_footprints', [])))} |",
             "| Manual visual review | Pending review of the actual PNG |", "",
             "## Sources and outstanding issues", "", "Assess source authority using the provenance records. Automated layout checks do not verify geographic accuracy.", ""]
    lines.extend("- " + str(x) for x in qa.get("errors", []) + qa.get("warnings", []))
    (project_dir / "output" / "quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


class App:
    def __init__(self, workspace: Path):
        self.workspace = workspace.expanduser().resolve()
        self.projects_dir = self.workspace / "projects"
        self.cache_dir = self.workspace / "cache"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.tasks = {}
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cartography")
        self.environment = environment_report()

    def examples(self):
        return [read_json(p) for p in sorted((APP_DIR / "examples").glob("*/example.json"))]

    def list_projects(self):
        rows = []
        for path in sorted(self.projects_dir.glob("*/project.json"), reverse=True):
            try:
                row = read_json(path)
                rows.append({k: row.get(k) for k in ("id", "title", "created_utc", "status")})
            except (ValueError, OSError):
                continue
        return rows[:100]

    def status(self):
        return {"version": VERSION, "environment": self.environment, "app_dir": str(APP_DIR),
                "workspace": str(self.workspace), "projects": self.list_projects(),
                "examples": self.examples(), "capabilities": {
                    "online": True, "offline_import": True, "offline_examples": True,
                    "geocoder": "Photon / OpenStreetMap", "point_location": False,
                    "ai_agent_embedded": False, "layout": "16:9", "exports": ["PNG", "SVG", "ZIP"],
                    "notice": "Online mode uses open data; verify boundaries and river names. The bundled example and local imports work offline."}}

    def project_path(self, project_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", str(project_id)):
            raise ValueError("Invalid project identifier.")
        path = self.projects_dir / project_id
        if not (path / "project.json").is_file():
            raise FileNotFoundError("Project not found.")
        return path

    def new_project(self, title):
        project_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
        path = self.projects_dir / project_id
        path.mkdir()
        meta = {"id": project_id, "title": str(title or "River and Lake Map")[:120],
                "created_utc": utc_now(), "status": "running", "app_version": VERSION}
        atomic_json(path / "project.json", meta)
        return path

    def submit(self, kind, params):
        with self.lock:
            active = sum(t["status"] in ("queued", "running") for t in self.tasks.values())
            if active >= 3:
                raise ValueError("Three mapping tasks are already queued. Wait for a task to finish.")
            task_id = uuid.uuid4().hex
            self.tasks[task_id] = {"id": task_id, "status": "queued", "progress": 0,
                                   "message": "Task queued", "logs": []}
        self.executor.submit(self.run_task, task_id, kind, params)
        return {"task_id": task_id}

    def progress(self, task_id, percent, message):
        with self.lock:
            task = self.tasks[task_id]
            task.update(progress=max(0, min(100, int(percent))), message=str(message))
            task["logs"].append({"time": datetime.now().strftime("%H:%M:%S"), "message": str(message)})
            task["logs"] = task["logs"][-150:]

    def run_task(self, task_id, kind, params):
        path = None
        try:
            with self.lock:
                self.tasks[task_id]["status"] = "running"
            callback = lambda p, m: self.progress(task_id, p, m)
            if self.environment["status"] != "ready":
                raise RuntimeError("Runtime validation failed: " + "; ".join(self.environment["errors"]))
            if kind == "example":
                example = next((x for x in self.examples() if x["id"] == params.get("id")), None)
                if not example:
                    raise ValueError("Bundled example not found.")
                path = self.new_project(example["title"])
                callback(10, "Copying the offline example and source records")
                source = APP_DIR / "examples" / example["id"]
                for item in source.iterdir():
                    if item.is_dir():
                        shutil.copytree(item, path / item.name)
                    elif item.name != "example.json":
                        shutil.copy2(item, path / item.name)
                if params.get("title"):
                    job = read_json(path / "map_job.json")
                    job["title"] = str(params["title"])[:120]
                    atomic_json(path / "map_job.json", job)
            elif kind == "rerender":
                prior = self.project_path(params.get("project_id", ""))
                job = read_json(prior / "map_job.json")
                changes = params.get("job")
                if changes is not None:
                    if not isinstance(changes, dict):
                        raise ValueError("Map configuration must be a JSON object.")
                    # Reuse known project layers; imported paths never gain filesystem access.
                    for role in ("lake", "rivers", "admin"):
                        changes[role + "_file"] = job.get(role + "_file")
                    changes["font_path"] = None
                    job = changes
                if params.get("title"):
                    job["title"] = str(params["title"])[:120]
                path = self.new_project(job["title"])
                for name in ("data_work", "data_raw"):
                    if (prior / name).is_dir():
                        shutil.copytree(prior / name, path / name)
                for name in ("sources.json", "data_provenance.json"):
                    if (prior / name).is_file():
                        shutil.copy2(prior / name, path / name)
                atomic_json(path / "map_job.json", job)
                callback(25, "Previous version preserved; generating a new version")
            else:
                from data_service import build_online_project, build_import_project
                path = self.new_project(params.get("title"))
                callback(5, "Preparing project data")
                fn = build_online_project if kind == "create" else build_import_project
                fn(path, params, progress=callback)
            qa = render_project(path, callback)
            meta = read_json(path / "project.json")
            meta.update(status=qa["status"], title=read_json(path / "map_job.json")["title"])
            atomic_json(path / "project.json", meta)
            self.create_archive(path)
            result = self.project_result(path.name)
            with self.lock:
                self.tasks[task_id].update(status=qa["status"], progress=100, result=result,
                    message="Map generated. Review the image and quality report." if not qa["errors"] else "Diagnostic preview generated. Resolve the reported issues and render again.",
                    error="; ".join(qa["errors"]) if qa["errors"] else None)
        except Exception as exc:
            message = str(exc) or type(exc).__name__
            if path:
                (path / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
                meta = read_json(path / "project.json")
                meta["status"] = "failed"
                atomic_json(path / "project.json", meta)
            with self.lock:
                self.tasks[task_id].update(status="failed", progress=100, message="Task incomplete", error=message)
            self.progress(task_id, 100, message)

    def create_archive(self, path):
        target = path / "project_export.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for item in sorted(path.rglob("*")):
                if not item.is_file() or item == target or item.suffix in (".tmp", ".log"):
                    continue
                if item.name == "map_job.json":
                    # Export a relocatable job rather than the installation's font path.
                    archive.writestr("map_job.json", (path / "map_job.portable.json").read_bytes())
                else:
                    archive.write(item, item.relative_to(path).as_posix())

    def project_result(self, project_id):
        path = self.project_path(project_id)
        meta = read_json(path / "project.json")
        qa_path = path / "output" / "qa.json"
        qa = read_json(qa_path) if qa_path.exists() else {"status": meta["status"], "errors": [], "warnings": []}
        preview = "output/map.png" if not qa.get("errors") else "output/diagnostic_preview.png"
        if not (path / preview).exists():
            preview = None
        files = []
        for rel, label in (("output/map.png", "Map PNG"), ("output/map.svg", "Map SVG"),
                           ("output/diagnostic_preview.png", "Diagnostic preview PNG"),
                           ("output/diagnostic_preview.svg", "Diagnostic preview SVG"),
                           ("output/qa.json", "Automated quality report"), ("output/quality_report.md", "Quality report"),
                           ("map_job.portable.json", "Portable map configuration"), ("sources.json", "Example source inventory"),
                           ("data_provenance.json", "Data provenance"), ("project_export.zip", "Complete project ZIP")):
            if (path / rel).is_file():
                files.append({"name": label, "filename": Path(rel).name,
                              "url": f"/api/artifact/{project_id}/{rel}"})
        return {"project_id": project_id, "title": meta["title"], "project_path": str(path), "project_dir": str(path),
                "status": qa.get("status"), "preview_url": f"/api/artifact/{project_id}/{preview}" if preview else None,
                "qa": qa, "downloads": files,
                "job": read_json(path / "map_job.json") if (path / "map_job.json").exists() else None}


class Handler(BaseHTTPRequestHandler):
    server_version = "RiverLakeCartography/1.0"

    def log_message(self, fmt, *args):
        pass

    @property
    def app(self):
        return self.server.app

    def common_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")

    def respond(self, code, payload, content_type="application/json; charset=utf-8"):
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8") if not isinstance(payload, bytes) else payload
        self.send_response(code)
        self.common_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def safe_request(self, require_token=False):
        port = self.server.server_address[1]
        valid_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in valid_hosts:
            raise PermissionError("Only local access is allowed.")
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://" + x for x in valid_hosts}:
            raise PermissionError("Request origin does not match.")
        if require_token and not secrets.compare_digest(self.headers.get("X-App-Token", ""), self.app.token):
            raise PermissionError("Session expired. Reopen the page using the application launcher.")

    def handle_error(self, exc):
        code = 403 if isinstance(exc, PermissionError) else 404 if isinstance(exc, FileNotFoundError) else 400
        self.respond(code, {"error": str(exc) or type(exc).__name__})

    def do_GET(self):
        try:
            path = unquote(urlsplit(self.path).path)
            self.safe_request(path.startswith("/api/"))
            if path == "/api/status":
                self.respond(200, self.app.status())
            elif path.startswith("/api/task/"):
                task_id = path.rsplit("/", 1)[-1]
                with self.app.lock:
                    if task_id not in self.app.tasks:
                        raise FileNotFoundError("Task not found.")
                    snapshot = json.loads(json.dumps(self.app.tasks[task_id], ensure_ascii=False))
                self.respond(200, snapshot)
            elif path.startswith("/api/projects/"):
                self.respond(200, self.app.project_result(path.rsplit("/", 1)[-1]))
            elif path.startswith("/api/artifact/"):
                parts = path.split("/", 4)
                if len(parts) != 5:
                    raise FileNotFoundError("Invalid file address.")
                root = self.app.project_path(parts[3]).resolve()
                target = (root / parts[4]).resolve()
                if not target.is_relative_to(root) or not target.is_file() or target.is_symlink():
                    raise FileNotFoundError("File not found.")
                ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                self.respond(200, target.read_bytes(), ctype)
            else:
                relative = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
                if relative not in ("index.html", "app.css", "app.js", "favicon.svg"):
                    raise FileNotFoundError("Page not found.")
                target = APP_DIR / "web" / relative
                data = target.read_bytes()
                if relative == "index.html":
                    data = data.replace(b"__APP_TOKEN__", self.app.token.encode("ascii"))
                self.respond(200, data, (mimetypes.guess_type(target.name)[0] or "text/plain") + "; charset=utf-8")
        except Exception as exc:
            self.handle_error(exc)

    def do_POST(self):
        try:
            self.safe_request(True)
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > MAX_BODY:
                raise ValueError("The import limit is 48 MB. Clip the spatial data before importing.")
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Request must use JSON.")
            params = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(params, dict):
                raise ValueError("Request body must be an object.")
            path = urlsplit(self.path).path
            if path == "/api/search":
                from data_service import search_places
                self.respond(200, {"results": search_places(params.get("query", ""), self.app.cache_dir)})
            elif path in ("/api/create", "/api/import", "/api/example", "/api/rerender"):
                self.respond(202, self.app.submit(path.rsplit("/", 1)[-1], params))
            elif path == "/api/shutdown":
                self.respond(200, {"status": "stopping"})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                raise FileNotFoundError("Endpoint not found.")
        except Exception as exc:
            self.handle_error(exc)


def self_test(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    env = environment_report()
    report = {"app_version": VERSION, "platform": sys.platform,
              "executable": sys.executable, "environment": env, "status": "failed"}
    if env["status"] == "ready":
        project = output_dir / ("example_" + uuid.uuid4().hex[:6])
        shutil.copytree(APP_DIR / "examples" / "shijiu", project)
        qa = render_project(project)
        report.update(status="passed" if not qa["errors"] else "failed", qa_status=qa["status"],
                      label_counts=qa.get("label_counts"), errors=qa["errors"],
                      image_size=qa.get("image_size_px_measured"), output_dir=str(project))
    atomic_json(output_dir / "self_test_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if report["status"] == "passed" else 1


def main():
    parser = argparse.ArgumentParser(description="River Lake Cartography")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    workspace = args.workspace or (documents_dir() / "RiverLakeMaps")
    cache = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".cache"))) / "RiverLakeCartography"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache / "matplotlib"))
    if args.self_test:
        return self_test(args.output_dir or (workspace / "self_test"))
    app = App(workspace)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    server.app = app
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    if sys.stdout:
        print(json.dumps({"url": url, "token": app.token, "workspace": str(app.workspace)}, ensure_ascii=False), flush=True)
    (cache / "last-session-url.txt").write_text(url, encoding="utf-8")
    if not args.no_browser:
        threading.Timer(.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.executor.shutdown(wait=False, cancel_futures=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        text = traceback.format_exc()
        location = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "RiverLakeCartography"
        location.mkdir(parents=True, exist_ok=True)
        (location / "startup-error.log").write_text(text, encoding="utf-8")
        if os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, "Application startup failed. Detailed log: \n" + str(location / "startup-error.log"), "River Lake Cartography", 16)
        if sys.stderr:
            print(text, file=sys.stderr)
        raise SystemExit(1)
