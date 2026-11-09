"use strict";

(() => {
  const $ = id => document.getElementById(id);
  const token = document.querySelector('meta[name="app-token"]').content;
  const state = { busy: false, selected: null, boundsEdited: false, examples: [], previewBlob: null, taskId: null, result: null, status: {}, disconnected: false };
  let toastTimer;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }
  function message(text, type = "error") {
    const box = $("global-message");
    box.textContent = text || "";
    box.className = "notice " + type;
    box.hidden = !text;
    if (text) box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
  function toast(text) {
    $("toast").textContent = text;
    $("toast").hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { $("toast").hidden = true; }, 4000);
  }
  function errorText(error) {
    if (typeof error === "string") return error;
    if (error && typeof error.message === "string") return error.message;
    if (error && typeof error.detail === "string") return error.detail;
    return JSON.stringify(error || "Unknown error");
  }
  async function request(path, payload) {
    const headers = { "X-App-Token": token };
    const options = { headers, cache: "no-store" };
    if (payload !== undefined) {
      options.method = "POST";
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(payload);
    }
    let response;
    try { response = await fetch(path, options); }
    catch (error) { throw new Error("Cannot connect to the local application. Make sure it is running and retry."); }
    const text = await response.text();
    let data;
    try { data = JSON.parse(text); }
    catch (error) { throw new Error("The application returned an unreadable result (HTTP " + response.status + "). Check the application log."); }
    if (!response.ok) throw new Error(errorText(data.error || data.message || ("Request failed: " + response.status)));
    return data;
  }
  function sameOriginURL(value) {
    const url = new URL(value, window.location.href);
    if (url.origin !== window.location.origin) throw new Error("The result URL does not belong to the local application. Retrieval stopped.");
    return url.href;
  }
  async function fetchBlob(url) {
    const response = await fetch(sameOriginURL(url), { headers: { "X-App-Token": token }, cache: "no-store" });
    if (!response.ok) throw new Error("Cannot read the result file (HTTP " + response.status + ").");
    return response.blob();
  }
  function setTab(name) {
    document.querySelectorAll("[data-tab]").forEach(button => {
      const active = button.dataset.tab === name;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
      $("panel-" + button.dataset.tab).hidden = !active;
    });
  }
  function setBusy(busy) {
    state.busy = busy;
    document.querySelectorAll(".action-button, #search-location, #try-example, #open-project, #project-select").forEach(button => {
      button.disabled = busy || (button.id === "open-project" && !$("project-select").value);
    });
  }
  function badge(text, type) {
    $("result-badge").textContent = text;
    $("result-badge").className = "badge badge-" + type;
  }
  function clearPreview() {
    if (state.previewBlob) URL.revokeObjectURL(state.previewBlob);
    state.previewBlob = null;
    state.result = null;
    $("map-preview").hidden = true;
    $("map-preview").removeAttribute("src");
    $("preview-empty").hidden = false;
    $("preview-stage").classList.remove("has-image");
    $("view-original").disabled = true;
    $("results-card").hidden = true;
    $("download-list").replaceChildren();
    $("qa-issues").replaceChildren();
  }
  function lines(value) {
    // Commas belong to qualified place names such as "Gaochun District, Nanjing".
    return Array.from(new Set(value.split(/[\n\r;\uFF1B]+/).map(x => x.trim()).filter(Boolean)));
  }
  function bboxFromForm() {
    const values = ["west", "south", "east", "north"].map(key => $("bbox-" + key).value.trim());
    if (values.every(value => value === "")) return null;
    if (values.some(value => value === "")) throw new Error("Provide all four extent values: west, south, east, and north.");
    const bounds = values.map(Number);
    if (bounds.some(value => !Number.isFinite(value))) throw new Error("Extent coordinates must be valid numbers.");
    if (bounds[0] < -180 || bounds[2] > 180 || bounds[1] < -90 || bounds[3] > 90 || bounds[0] >= bounds[2] || bounds[1] >= bounds[3]) {
      throw new Error("Check the extent: west must be less than east, south less than north, and all values within valid longitude/latitude ranges.");
    }
    return bounds;
  }
  function resolution(id) {
    const width = Number($(id).value) || 3840;
    return { width_px: width, height_px: Math.round(width * 9 / 16) };
  }
  function chooseLocation(item, button) {
    if (!Array.isArray(item.bbox) || item.bbox.length !== 4) {
      message("This result has no valid extent. Choose another result or enter the extent manually.");
      return;
    }
    state.selected = item;
    state.boundsEdited = false;
    ["west", "south", "east", "north"].forEach((key, index) => { $("bbox-" + key).value = Number(item.bbox[index]).toFixed(6); });
    $("selected-location").replaceChildren(el("div", "", "Selected: " + item.name));
    if (item.bbox_inferred) {
      $("selected-location").append(el("p", "field-hint", "This result provides a centre point. The proposed extent is estimated; review and adjust its coordinates."));
      const label = el("label", "check-row");
      const checkbox = el("input");
      checkbox.type = "checkbox";
      checkbox.id = "confirm-estimated-bbox";
      label.append(checkbox, el("span", "", "Confirm the estimated extent"));
      $("selected-location").append(label);
      $("bbox-west").closest("details").open = true;
    }
    $("selected-location").hidden = false;
    document.querySelectorAll(".search-result").forEach(node => node.classList.toggle("selected", node === button));
  }
  async function searchLocation() {
    const query = $("map-query").value.trim();
    if (!query) { message("Enter a place name, preferably with its city or region."); $("map-query").focus(); return; }
    message("");
    const button = $("search-location");
    button.disabled = true;
    button.textContent = "Searching";
    $("search-results").replaceChildren(el("div", "search-empty", "Searching the public place-name service..."));
    $("search-results").hidden = false;
    try {
      const data = await request("/api/search", { query });
      if (query !== $("map-query").value.trim()) return;
      const results = Array.isArray(data.results) ? data.results : [];
      $("search-results").replaceChildren();
      if (!results.length) $("search-results").append(el("div", "search-empty", "No matching place was found. Add its city or region, try another name, or enter the extent."));
      results.forEach(item => {
        const resultButton = el("button", "search-result");
        resultButton.type = "button";
        resultButton.append(el("span", "", item.name || item.display_name || "Unnamed place"));
        if (item.type) resultButton.append(el("small", "", item.type));
        resultButton.addEventListener("click", () => chooseLocation(item, resultButton));
        $("search-results").append(resultButton);
      });
    } catch (error) {
      $("search-results").replaceChildren(el("div", "search-empty", "Search did not complete. Refine the name and retry, or use existing data."));
      message(error.message);
    } finally { button.disabled = state.busy; button.textContent = "Search"; }
  }
  async function startTask(endpoint, payload) {
    if (state.busy) return;
    message("");
    setBusy(true);
    clearPreview();
    $("preview-title").textContent = payload.title || "Rendering the map";
    $("preview-loading").hidden = false;
    $("preview-loading-message").textContent = "Preparing data";
    $("progress-card").hidden = false;
    $("progress-title").textContent = "Rendering";
    $("progress-percent").textContent = "";
    $("progress-bar").style.width = "0%";
    $("progress-message").textContent = "Submitting the task...";
    $("task-log").textContent = "";
    badge("Processing", "busy");
    try {
      const data = await request(endpoint, payload);
      if (!data.task_id) throw new Error("The application returned no task ID, so this task cannot be tracked.");
      state.taskId = data.task_id;
      await pollTask(data.task_id);
    } catch (error) {
      badge("Task incomplete", "error");
      $("progress-title").textContent = "Task incomplete";
      $("progress-message").textContent = error.message;
      $("preview-loading").hidden = true;
      message(error.message);
    } finally {
      state.taskId = null;
      setBusy(false);
      refreshStatus(false).catch(() => {});
    }
  }
  function logText(logs) {
    if (!Array.isArray(logs)) return typeof logs === "string" ? logs : "";
    return logs.map(item => typeof item === "string" ? item : [item.time || item.timestamp || "", item.message || JSON.stringify(item)].filter(Boolean).join(" ")).join("\n");
  }
  async function pollTask(taskId) {
    let failures = 0;
    while (state.taskId === taskId) {
      let task;
      try { task = await request("/api/task/" + encodeURIComponent(taskId)); failures = 0; }
      catch (error) {
        failures += 1;
        if (failures >= 3) throw error;
        $("progress-message").textContent = "Progress is temporarily unavailable. Reconnecting...";
        await new Promise(resolve => setTimeout(resolve, 1500));
        continue;
      }
      const progress = Number(task.progress);
      if (Number.isFinite(progress)) {
        const bounded = Math.min(100, Math.max(0, progress));
        $("progress-bar").style.width = bounded + "%";
        $("progress-percent").textContent = Math.round(bounded) + "%";
      }
      const currentMessage = task.message || "Processing data and the map...";
      $("progress-message").textContent = currentMessage;
      $("preview-loading-message").textContent = currentMessage;
      const log = logText(task.logs);
      if (log) { $("task-log").textContent = log; $("task-log").scrollTop = $("task-log").scrollHeight; }
      if (["completed", "completed_with_warnings", "done", "success", "failed", "cancelled"].includes(task.status)) {
        $("preview-loading").hidden = true;
        if (task.result) await showResult(task.result, task.status);
        if (task.status === "failed" || task.status === "cancelled") {
          const reason = errorText(task.error || task.message || "This task did not complete. Review the processing log.");
          $("progress-title").textContent = task.result ? "Draft requires revision" : "Task incomplete";
          if (!task.result) badge("Task incomplete", "error");
          message(reason);
          return;
        }
        if (!task.result) throw new Error("The task ended without returning a map result. Review the processing log.");
        $("progress-title").textContent = "Processing complete";
        $("progress-bar").style.width = "100%";
        $("progress-percent").textContent = "100%";
        return;
      }
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }
  async function showResult(result, taskStatus = "completed") {
    state.result = result;
    const qa = result.qa || {};
    const errors = Array.isArray(qa.errors) ? qa.errors : [];
    const warnings = Array.isArray(qa.warnings) ? qa.warnings : [];
    const failed = taskStatus === "failed" || qa.status === "failed" || errors.length > 0;
    const withWarnings = taskStatus === "completed_with_warnings" || qa.status === "completed_with_warnings" || warnings.length > 0;
    $("preview-title").textContent = result.title || "Map working draft";
    badge(failed ? "Draft requires revision" : withWarnings ? "Draft with notices" : "Draft generated", failed ? "error" : withWarnings ? "warning" : "success");
    $("project-reference").textContent = result.project_id ? "Project " + result.project_id : "";
    $("results-card").hidden = false;
    $("revision-title").value = result.title || "";
    $("revision-job").value = result.job ? JSON.stringify(result.job, null, 2) : "";
    $("revision-job").disabled = !result.job;
    $("rerender-form").hidden = !result.project_id;
    if (result.preview_url) {
      try {
        const blob = await fetchBlob(result.preview_url);
        if (state.previewBlob) URL.revokeObjectURL(state.previewBlob);
        state.previewBlob = URL.createObjectURL(blob);
        $("map-preview").src = state.previewBlob;
        $("map-preview").alt = result.title || "Generated thematic map";
        $("map-preview").hidden = false;
        $("preview-empty").hidden = true;
        $("preview-stage").classList.add("has-image");
        $("view-original").disabled = false;
        $("preview-caption").textContent = failed ? "Diagnostic draft | Resolve the issues in the quality report" : "Rendered result | Open the original to inspect river labels, administrative names, and the legend";
      } catch (error) { message("Results are saved, but the preview could not be loaded: " + error.message); }
    }
    $("download-list").replaceChildren();
    (result.downloads || []).forEach(item => {
      if (!item.url) return;
      const button = el("button", "download-button", "↓ " + (item.name || "Download file"));
      button.type = "button";
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          const blob = await fetchBlob(item.url);
          const url = URL.createObjectURL(blob);
          const link = el("a");
          link.href = url;
          link.download = item.filename || decodeURIComponent(new URL(item.url, window.location.href).pathname.split("/").pop()) || "map-output";
          document.body.append(link);
          link.click();
          link.remove();
          setTimeout(() => URL.revokeObjectURL(url), 60000);
        } catch (error) { message(error.message); }
        finally { button.disabled = false; }
      });
      $("download-list").append(button);
    });
    const counts = qa.label_counts || {};
    const explicitLakes = Number(counts.requested_lakes || 0) > 0;
    const stats = [["River labels", counts.placed_rivers, counts.requested_rivers, "Placed / requested"], ["Administrative labels", counts.placed_admin, counts.requested_admin, "Placed / requested"], ["Lake labels", explicitLakes ? (counts.placed_requested_lakes ?? counts.placed_lake_labels_total) : counts.placed_lake_labels_total, explicitLakes ? counts.requested_lakes : counts.automatic_lake_label_candidates, explicitLakes ? "Placed / requested" : "Placed / candidate"]];
    $("qa-summary").replaceChildren();
    stats.forEach(([label, placed, requested, note]) => {
      const cell = el("div", "qa-stat");
      const meaningful = Number.isFinite(Number(placed)) && placed !== undefined;
      const display = placed === 0 && requested === 0 ? "Not requested" : meaningful ? (String(placed) + (Number.isFinite(Number(requested)) && requested !== undefined ? " / " + requested : "")) : "—";
      cell.append(el("b", "", display), el("span", "", label + " · " + note));
      $("qa-summary").append(cell);
    });
    $("qa-issues").replaceChildren();
    errors.forEach(value => $("qa-issues").append(el("div", "qa-issue error", "Needs revision: " + errorText(value))));
    warnings.forEach(value => $("qa-issues").append(el("div", "qa-issue warning", "Notice: " + errorText(value))));
    (Array.isArray(result.data_warnings) ? result.data_warnings : []).forEach(value => $("qa-issues").append(el("div", "qa-issue warning", "Data notice: " + errorText(value))));
    if (!errors.length && !warnings.length) {
      const verified = !failed && ["completed", "completed_with_warnings"].includes(qa.status);
      $("qa-issues").append(el("div", "qa-issue " + (verified ? "good" : "warning"), verified ? "Automated checks reported no issues. Verify place names and source suitability against the map." : "Valid automated checks have not completed. Read the log and inspect the actual image."));
    }
    $("qa-json").textContent = JSON.stringify(qa, null, 2);
  }
  async function readJSONFile(inputId) {
    const file = $(inputId).files[0];
    if (!file) return null;
    if (file.size > 25 * 1024 * 1024) throw new Error(file.name + " exceeds 25 MB. Clip it to the local map extent first.");
    try { return JSON.parse((await file.text()).replace(/^\uFEFF/, "")); }
    catch (error) { throw new Error(file.name + " is not a valid JSON file. Check its contents and encoding."); }
  }
  function renderExamples(examples) {
    state.examples = Array.isArray(examples) ? examples : [];
    $("example-list").replaceChildren();
    if (!state.examples.length) {
      $("example-list").append(el("p", "field-hint", "No bundled example is available. Use online data or import local layers."));
      $("try-example").disabled = true;
      return;
    }
    $("try-example").disabled = state.busy;
    state.examples.forEach(item => {
      const card = el("article", "example-card");
      card.append(el("span", "example-icon", "BUNDLED EXAMPLE"), el("h3", "", item.title || item.id), el("p", "", item.description || "Generate a reviewable working map from the bundled real-world data and configuration."));
      const button = el("button", "button button-secondary action-button", "Render example map →");
      button.type = "button";
      button.disabled = state.busy;
      button.addEventListener("click", () => startTask("/api/example", { id: item.id, title: item.title }));
      card.append(button);
      $("example-list").append(card);
    });
  }
  async function refreshStatus(first = false) {
    try {
      const data = await request("/api/status");
      state.status = data;
      state.disconnected = false;
      $("connection-dot").className = "connection-dot connected";
      $("connection-label").textContent = "Local app connected";
      const version = data.version ? "v" + String(data.version).replace(/^v/, "") : "";
      $("app-version").textContent = version;
      $("footer-version").textContent = version;
      const selected = $("project-select").value;
      $("project-select").replaceChildren(el("option", "", "Existing projects"));
      $("project-select").options[0].value = "";
      (data.projects || []).forEach(project => {
        const option = el("option", "", project.title || project.id);
        option.value = project.id;
        $("project-select").append(option);
      });
      if (selected) $("project-select").value = selected;
      $("open-project").disabled = state.busy || !$("project-select").value;
      if (data.examples) renderExamples(data.examples);
      if (first && data.environment && data.environment.status === "not_ready") {
        message("Runtime checks failed: " + (data.environment.errors || []).map(errorText).join("; "));
      }
    } catch (error) {
      state.disconnected = true;
      $("connection-dot").className = "connection-dot error";
      $("connection-label").textContent = "Local app disconnected";
      if (first) message(error.message);
      throw error;
    }
  }
  async function openProject() {
    const id = $("project-select").value;
    if (!id || state.busy) return;
    message("");
    setBusy(true);
    clearPreview();
    $("preview-loading").hidden = false;
    $("preview-loading-message").textContent = "Opening existing results";
    try {
      const result = await request("/api/projects/" + encodeURIComponent(id));
      await showResult(result.result || result);
      $("progress-card").hidden = true;
    } catch (error) { message(error.message); }
    finally { $("preview-loading").hidden = true; setBusy(false); }
  }

  document.querySelectorAll("[data-tab]").forEach(button => button.addEventListener("click", () => setTab(button.dataset.tab)));
  $("search-location").addEventListener("click", searchLocation);
  $("map-query").addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); searchLocation(); } });
  $("map-query").addEventListener("input", () => {
    if (state.selected) ["west", "south", "east", "north"].forEach(key => { $("bbox-" + key).value = ""; });
    state.selected = null;
    state.boundsEdited = false;
    $("selected-location").hidden = true;
  });
  ["west", "south", "east", "north"].forEach(key => $("bbox-" + key).addEventListener("input", () => { state.boundsEdited = true; }));
  $("online-form").addEventListener("submit", async event => {
    event.preventDefault();
    try {
      const bbox = bboxFromForm();
      const query = $("map-query").value.trim();
      if (!bbox) throw new Error("Search for and select a place, or enter the complete geographic extent.");
      if (state.selected && state.selected.bbox_inferred && !state.boundsEdited && !$("confirm-estimated-bbox")?.checked) throw new Error("Review and confirm the estimated extent, or adjust the coordinates manually.");
      const payload = { title: $("map-title").value.trim(), mode: $("map-mode").value, query, bbox, admin_queries: lines($("admin-queries").value), river_names: lines($("river-names").value), ...resolution("online-resolution") };
      if (state.selected) payload.selected_place = { ...state.selected };
      await startTask("/api/create", payload);
    } catch (error) { message(error.message); }
  });
  document.querySelectorAll("[data-layer]").forEach(input => input.addEventListener("change", () => {
    const file = input.files[0];
    $(input.dataset.layer + "-file-name").textContent = file ? file.name : "Choose a GeoJSON file";
    input.parentElement.classList.toggle("has-file", Boolean(file));
  }));
  $("import-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (state.busy) return;
    try {
      const title = $("import-title").value.trim();
      if (!title) throw new Error("Enter a map title.");
      if (!$("confirm-crs").checked) throw new Error("Confirm that the data uses EPSG:4326. Verify and transform data with an unknown coordinate system before importing.");
      const layers = {};
      const records = {};
      for (const role of ["lake", "rivers", "admin"]) {
        const layer = await readJSONFile(role + "-file");
        if (!layer) continue;
        layers[role] = layer;
        const sourceName = $(role + "-source-name").value.trim() || "User-provided data";
        records[role] = { source_name: sourceName, source_url: $(role + "-source-url").value.trim(), year: $(role + "-source-year").value.trim() || "Unknown", license: "Terms of use must be confirmed by the data provider", authority_status: "User-provided data; authoritative status requires verification", attribution: sourceName, notes: "Imported through the desktop app; the user declared EPSG:4326." };
      }
      if (!Object.keys(layers).length) throw new Error("Select at least one lake, river, or administrative GeoJSON file.");
      const job = await readJSONFile("job-file");
      const payload = { title, layers, source_records: records, source_crs: "EPSG:4326", river_names: lines($("import-river-names").value), ...resolution("import-resolution") };
      if ($("import-admin-level").value) payload.admin_level = $("import-admin-level").value;
      if (job) payload.job = job;
      await startTask("/api/import", payload);
    } catch (error) { message(error.message); }
  });
  $("try-example").addEventListener("click", () => { setTab("examples"); if (state.examples.length === 1) { const example = state.examples[0]; startTask("/api/example", { id: example.id, title: example.title }); } else $("example-list").scrollIntoView({ behavior: "smooth", block: "nearest" }); });
  $("project-select").addEventListener("change", () => { $("open-project").disabled = state.busy || !$("project-select").value; if (window.innerWidth <= 650 && $("project-select").value) openProject(); });
  $("open-project").addEventListener("click", openProject);
  $("rerender-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (state.busy || !state.result?.project_id) return;
    try {
      const payload = { project_id: state.result.project_id };
      const title = $("revision-title").value.trim();
      if (title && title !== state.result.title) payload.title = title;
      const jobText = $("revision-job").value.trim();
      if (jobText && jobText !== JSON.stringify(state.result.job, null, 2)) {
        try { payload.job = JSON.parse(jobText); }
        catch (error) { throw new Error("The advanced configuration is not valid JSON. Check commas, brackets, and quotation marks."); }
      }
      await startTask("/api/rerender", payload);
    } catch (error) { message(error.message); }
  });
  $("copy-ai-prompt").addEventListener("click", async () => {
    const result = state.result;
    const job = result?.job || {};
    const title = result?.title || $("map-title").value.trim() || $("import-title").value.trim() || "Determine a title from my map requirements";
    const project = result?.project_path || result?.project_dir || state.status.workspace || "Open this map's project folder in local Codex";
    const python = state.status.environment?.executable || "Use the Python environment already validated for this project";
    const prompt = [
      "$river-lake-cartography", "", "Continue this River Lake Cartography task. Make the requested changes, render the map, and inspect the actual output.", "",
      "Map subject: " + title,
      "Project location: " + project,
      "Existing project ID: " + (result?.project_id || "Not generated yet"),
      "Current Python: " + python,
      "Map location: " + ($("map-query").value.trim() || "Verify using the existing map configuration and data"),
      "Required administrative areas: " + (lines($("admin-queries").value).join(", ") || "Verify against the task extent and available data"),
      "Required rivers: " + (lines($("river-names").value || $("import-river-names").value).join(", ") || "Select and verify against the actual data"),
      "", "Changes I would like to make:", "[Enter the specific changes here]", "",
      "Execution requirements:",
      "1. Read the available river-lake-cartography skill, map configuration, and source records. If the skill is unavailable, say so and read the app's bundled cartographic rules and scripts.",
      "2. Reuse verified data and the project environment. Find traceable sources for missing data and record source, year, coordinate system, and scope. Base every geographic feature on real data.",
      "3. Place river names along the actual channels; never use river-name leader lines. Keep the legend inside the lower-left main map frame. Label provinces, cities, and counties according to their verified hierarchy and actual regions.",
      "4. Apply the requested changes while preserving confirmed content and previous results. Keep spatial relationships correct when changing extent, scale, label positions, or font sizes.",
      "5. Run the renderer, read the quality report, and open the PNG to inspect river names, administrative labels, the legend, and overall readability. Report failed and unperformed checks honestly.",
      "6. Deliver the new PNG, SVG, configuration, and a short change log. Identify data issues still requiring verification. Monitoring-point positioning remains deferred.",
      "", "Current application status: " + (result ? (result.status || result.qa?.status || "Draft generated") : "No map generated yet"),
      "Existing map configuration summary: " + JSON.stringify({ title: job.title, extent_wgs84: job.extent_wgs84, source_crs: job.source_crs, render_crs: job.render_crs }),
      "", "This prompt is intended for local Codex. Continue according to my additional change requests."
    ].join("\n");
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(prompt);
      else {
        const area = el("textarea");
        area.value = prompt;
        area.style.position = "fixed";
        area.style.left = "-10000px";
        document.body.append(area);
        area.select();
        if (!document.execCommand("copy")) throw new Error("The browser did not allow copying");
        area.remove();
      }
      toast("Prompt copied. Paste it into local Codex and add your requested changes.");
    } catch (error) {
      const blob = new Blob([prompt], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = el("a");
      link.href = url;
      link.download = "Codex-Cartography-Prompt.txt";
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      toast("The browser blocked copying. The prompt was downloaded as a text file instead.");
    }
  });
  $("view-original").addEventListener("click", () => { if (state.previewBlob) window.open(state.previewBlob, "_blank", "noopener"); });
  $("shutdown").addEventListener("click", async () => {
    if (!window.confirm(state.busy ? "A map is being processed. Exit the local application?" : "Exit River Lake Cartography?")) return;
    try { await request("/api/shutdown", {}); }
    catch (error) { if (!/Cannot connect/.test(error.message)) { message(error.message); return; } }
    state.taskId = null;
    setBusy(true);
    $("preview-loading").hidden = true;
    $("connection-dot").className = "connection-dot";
    $("connection-label").textContent = "Application stopped";
    message("The local application has stopped. You can close this page. Launch the app again to resume.", "success");
    toast("Application stopped");
  });
  window.addEventListener("beforeunload", () => { if (state.previewBlob) URL.revokeObjectURL(state.previewBlob); });
  refreshStatus(true).catch(() => {});
})();
