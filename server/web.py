"""WSGI app for the Vision OS local browser shell."""

from __future__ import annotations

import json
from html import escape
from urllib.parse import unquote
import webbrowser
from wsgiref.simple_server import make_server

from server.editors import WorkspaceEditorError
from server.launchpad import LaunchpadService
from server.store import LiveStateStore


class LaunchpadApp:
    """Serve the Launchpad and workspace shell over a local browser session."""

    def __init__(self, service: LaunchpadService, live_state_store: LiveStateStore | None = None) -> None:
        self.service = service
        self.live_state_store = live_state_store

    def __call__(self, environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")
        if path == "/" and method == "GET":
            return self._html_response(start_response, _render_launchpad(self.service.build_snapshot()))
        if path == "/api/launchpad" and method == "GET":
            payload = json.dumps(self.service.build_snapshot(), indent=2)
            return self._json_response(start_response, payload)
        if path.startswith("/api/workspaces/") and path.endswith("/live") and method == "GET":
            workspace_id = unquote(path.removeprefix("/api/workspaces/").removesuffix("/live").rstrip("/"))
            return self._json_response(start_response, json.dumps(self._live_snapshot(workspace_id), indent=2))
        if path.startswith("/api/workspaces/") and path.endswith("/preview") and method == "GET":
            workspace_id = unquote(path.removeprefix("/api/workspaces/").removesuffix("/preview").rstrip("/"))
            return self._preview_response(start_response, workspace_id)
        if path.startswith("/api/workspaces/") and path.endswith("/start") and method == "POST":
            workspace_id = unquote(path.removeprefix("/api/workspaces/").removesuffix("/start").rstrip("/"))
            try:
                payload = self.service.start_workspace(workspace_id)
            except KeyError:
                return self._json_error(start_response, "404 Not Found", f"No saved space found for {workspace_id}.")
            except RuntimeError as exc:
                return self._json_error(start_response, "409 Conflict", str(exc))
            return self._json_response(start_response, json.dumps(payload, indent=2))
        if path.startswith("/api/workspaces/") and path.endswith("/start-recording") and method == "POST":
            workspace_id = unquote(path.removeprefix("/api/workspaces/").removesuffix("/start-recording").rstrip("/"))
            try:
                payload = self.service.start_workspace_with_recording(workspace_id)
            except KeyError:
                return self._json_error(start_response, "404 Not Found", f"No saved space found for {workspace_id}.")
            except RuntimeError as exc:
                return self._json_error(start_response, "409 Conflict", str(exc))
            return self._json_response(start_response, json.dumps(payload, indent=2))
        if path.startswith("/api/workspaces/") and path.endswith("/validate") and method == "POST":
            workspace_id = unquote(path.removeprefix("/api/workspaces/").removesuffix("/validate").rstrip("/"))
            try:
                payload = self.service.validate_workspace(workspace_id)
            except KeyError:
                return self._json_error(start_response, "404 Not Found", f"No saved space found for {workspace_id}.")
            except RuntimeError as exc:
                return self._json_error(start_response, "409 Conflict", str(exc))
            return self._json_response(start_response, json.dumps(payload, indent=2))
        if path.startswith("/api/workspaces/") and path.endswith("/integrations") and method == "GET":
            workspace_id = unquote(path.removeprefix("/api/workspaces/").removesuffix("/integrations").rstrip("/"))
            try:
                payload = self.service.load_workspace_integrations(workspace_id)
            except KeyError:
                return self._json_error(start_response, "404 Not Found", f"No saved space found for {workspace_id}.")
            except WorkspaceEditorError as exc:
                return self._json_error(start_response, "400 Bad Request", str(exc))
            return self._json_response(start_response, json.dumps(payload, indent=2))
        if path.startswith("/api/workspaces/") and path.endswith("/integrations") and method == "POST":
            workspace_id = unquote(path.removeprefix("/api/workspaces/").removesuffix("/integrations").rstrip("/"))
            try:
                request_payload = self._read_json_body(environ)
                payload = self.service.save_workspace_integrations(workspace_id, request_payload.get("targets", []))
            except KeyError:
                return self._json_error(start_response, "404 Not Found", f"No saved space found for {workspace_id}.")
            except WorkspaceEditorError as exc:
                return self._json_error(start_response, "400 Bad Request", str(exc))
            return self._json_response(start_response, json.dumps(payload, indent=2))
        if path == "/api/runtime/stop" and method == "POST":
            try:
                payload = self.service.stop_workspace()
            except RuntimeError as exc:
                return self._json_error(start_response, "409 Conflict", str(exc))
            return self._json_response(start_response, json.dumps(payload, indent=2))
        if path.startswith("/workspaces/") and method == "GET":
            workspace_id = unquote(path.removeprefix("/workspaces/"))
            workspace_surface = self.service.build_workspace_surface(workspace_id)
            if workspace_surface is None:
                return self._not_found(start_response, f"No saved space found for {workspace_id}.")
            return self._html_response(start_response, _render_workspace(workspace_surface))
        return self._not_found(start_response, f"Unknown route: {path}")

    def _html_response(self, start_response, document: str):
        body = document.encode("utf-8")
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body)))])
        return [body]

    def _json_response(self, start_response, payload: str):
        body = payload.encode("utf-8")
        start_response(
            "200 OK",
            [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))],
        )
        return [body]

    def _json_error(self, start_response, status: str, message: str):
        body = json.dumps({"error": message}, indent=2).encode("utf-8")
        start_response(
            status,
            [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))],
        )
        return [body]

    def _not_found(self, start_response, message: str):
        document = _base_document(
            "Vision OS",
            f"""
            <main class="page-shell">
              <section class="hero-panel">
                <p class="eyebrow">Workspace not found</p>
                <h1>{escape(message)}</h1>
                <p class="lede">Return to the Launchpad to choose another saved space.</p>
                <a class="primary-link" href="/">Back to Launchpad</a>
              </section>
            </main>
            """,
        )
        body = document.encode("utf-8")
        start_response(
            "404 Not Found",
            [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body)))],
        )
        return [body]

    def _live_snapshot(self, workspace_id: str) -> dict[str, object]:
        if self.live_state_store is None:
            return {"active": False}
        snapshot = self.live_state_store.load_snapshot()
        if snapshot is None or snapshot.workspace_id != workspace_id:
            return {"active": False}
        payload = snapshot.to_dict()
        payload["active"] = True
        return payload

    def _preview_response(self, start_response, workspace_id: str):
        if self.live_state_store is None:
            return self._not_found(start_response, f"No preview is available for {workspace_id}.")
        snapshot = self.live_state_store.load_snapshot()
        preview = self.live_state_store.load_preview()
        if snapshot is None or snapshot.workspace_id != workspace_id or preview is None:
            return self._not_found(start_response, f"No preview is available for {workspace_id}.")
        start_response(
            "200 OK",
            [("Content-Type", "image/jpeg"), ("Content-Length", str(len(preview)))],
        )
        return [preview]

    def _read_json_body(self, environ) -> dict[str, object]:
        content_length = environ.get("CONTENT_LENGTH", "0") or "0"
        try:
            size = int(content_length)
        except ValueError as exc:
            raise WorkspaceEditorError("Invalid request body length.") from exc
        raw_body = environ["wsgi.input"].read(size)
        if not raw_body:
            return {}
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise WorkspaceEditorError("Request body must be valid JSON.") from exc
        if not isinstance(payload, dict):
            raise WorkspaceEditorError("Request body root must be an object.")
        return payload


def _render_launchpad(snapshot: dict[str, object]) -> str:
    action_cards = "\n".join(
        f"""
        <article class="card action-card">
          <p class="card-kicker">Primary action</p>
          <h3>{escape(action["title"])}</h3>
          <p>{escape(action["description"])}</p>
          <code>{escape(action["command"])}</code>
        </article>
        """
        for action in snapshot["primary_actions"]
    )
    workspace_cards = "\n".join(
        f"""
        <a class="card workspace-card" href="{escape(workspace["href"])}">
          <p class="card-kicker">{escape(workspace["source_mode"])}</p>
          <h3>{escape(workspace["name"])}</h3>
          <p class="status-row">
            <span>Profile: {escape(workspace["profile_id"] or "none")}</span>
            <span>Validation: {escape(workspace["validation_state"])}</span>
            <span>Last run: {escape(workspace["last_run_state"])}</span>
          </p>
          <p>{escape(workspace["validation_summary"] or "Run setup validation to capture readiness and health.")}</p>
        </a>
        """
        for workspace in snapshot["workspaces"]
    )
    if not workspace_cards:
        workspace_cards = """
        <article class="card empty-card">
          <p class="card-kicker">No saved spaces yet</p>
          <h3>Start with guided setup</h3>
          <p>Use <code>python app.py --setup</code> to create your first saved space, then come back here to launch it.</p>
        </article>
        """

    session_cards = "\n".join(
        f"""
        <a class="card session-card" href="{escape(session["href"])}">
          <p class="card-kicker">{escape(session["state"])}</p>
          <h3>{escape(session["workspace_name"])}</h3>
          <p>Session {escape(session["session_id"])} opened from {escape(session["workspace_id"])}</p>
        </a>
        """
        for session in snapshot["recent_sessions"]
    )
    if not session_cards:
        session_cards = """
        <article class="card empty-card">
          <p class="card-kicker">No recent sessions</p>
          <h3>Runs appear here automatically</h3>
          <p>Live runs, replays, and validations will populate recent history once you use the runtime.</p>
        </article>
        """

    content = f"""
    <main class="page-shell">
      <section class="hero-panel">
        <div>
          <p class="eyebrow">Vision OS Launchpad</p>
          <h1>{escape(str(snapshot["title"]))}</h1>
          <p class="lede">Operate saved spaces, recover your last sessions, and move into the full workspace without living in the terminal.</p>
        </div>
        <div class="hero-stats">
          <article class="stat-card">
            <span class="stat-label">Saved spaces</span>
            <strong>{snapshot["workspace_count"]}</strong>
          </article>
          <article class="stat-card">
            <span class="stat-label">Recent sessions</span>
            <strong>{snapshot["recent_session_count"]}</strong>
          </article>
        </div>
      </section>
      <section class="grid-section">
        <header class="section-header">
          <p class="eyebrow">Start here</p>
          <h2>Primary actions</h2>
        </header>
        <div class="card-grid card-grid-four">{action_cards}</div>
      </section>
      <section class="grid-section">
        <header class="section-header">
          <p class="eyebrow">Saved spaces</p>
          <h2>Open a configured environment</h2>
        </header>
        <div class="card-grid">{workspace_cards}</div>
      </section>
      <section class="grid-section">
        <header class="section-header">
          <p class="eyebrow">Recent activity</p>
          <h2>Pick up where the last run ended</h2>
        </header>
        <div class="card-grid">{session_cards}</div>
      </section>
    </main>
    """
    return _base_document(str(snapshot["title"]), content)


def _render_workspace(surface: dict[str, object]) -> str:
    workspace = surface["workspace"]
    status = surface["status"]
    tabs = "\n".join(f"<li>{escape(tab)}</li>" for tab in surface["tabs"])
    content = f"""
    <main class="page-shell">
      <section class="hero-panel workspace-panel">
        <div>
          <p class="eyebrow">Saved space</p>
          <h1>{escape(workspace["name"])}</h1>
          <p class="lede">This workspace shell is ready for the upcoming live surface. The tab model is already in place so the Launchpad can hand control off cleanly.</p>
          <a class="primary-link" href="/">Back to Launchpad</a>
        </div>
        <div class="hero-stats">
          <article class="stat-card">
            <span class="stat-label">Source</span>
            <strong>{escape(workspace["source_mode"])}</strong>
          </article>
          <article class="stat-card">
            <span class="stat-label">Validation</span>
            <strong>{escape(status["validation_state"])}</strong>
          </article>
          <article class="stat-card">
            <span class="stat-label">Last run</span>
            <strong>{escape(status["last_run_state"])}</strong>
          </article>
        </div>
      </section>
      <section class="workspace-shell">
        <article class="card workspace-preview">
          <p class="card-kicker">Live preview</p>
          <h2>Workspace monitor</h2>
          <img id="live-preview" class="preview-frame" alt="Live Vision OS preview" src="/api/workspaces/{escape(workspace["workspace_id"])}/preview">
          <p id="preview-caption">Open a live run for this space to populate the browser preview.</p>
        </article>
        <article class="card workspace-tabs">
          <p class="card-kicker">Workspace navigation</p>
          <h2>Operator flow</h2>
          <ul class="tab-list">{tabs}</ul>
        </article>
        <article class="card workspace-status">
          <p class="card-kicker">Live state</p>
          <h2 id="live-scene-label">Awaiting session</h2>
          <p id="live-summary">{escape(status["validation_summary"] or "No validation recorded yet")}</p>
          <p id="live-metrics">Profile: {escape(workspace["profile_id"] or "none")} • Policy: {escape(workspace["policy_name"] or "default")}</p>
        </article>
        <article class="card workspace-events">
          <p class="card-kicker">Recent activity</p>
          <h2>Events and warnings</h2>
          <div class="workspace-controls">
            <button id="start-workspace" type="button">Start</button>
            <button id="record-workspace" type="button" class="secondary-button">Start + Record</button>
            <button id="validate-workspace" type="button" class="secondary-button">Validate</button>
            <button id="stop-workspace" type="button" class="secondary-button">Stop</button>
          </div>
          <ul id="live-events" class="tab-list">
            <li>No live session yet.</li>
          </ul>
        </article>
        <article class="card workspace-integrations">
          <p class="card-kicker">Integration builder</p>
          <h2>Dispatch targets</h2>
          <p id="integration-summary">Load a file-backed integration set for this workspace, then save updates without dropping back to raw YAML.</p>
          <p id="integration-path" class="editor-note">Preparing integrations path...</p>
          <div id="integration-targets" class="editor-stack">
            <p class="editor-empty">No integration targets loaded yet.</p>
          </div>
          <div class="workspace-controls">
            <button id="add-integration" type="button">Add integration</button>
            <button id="save-integrations" type="button" class="secondary-button">Save integrations</button>
          </div>
        </article>
      </section>
      <script>
        const workspaceId = {json.dumps(workspace["workspace_id"])};
        const sceneLabel = document.getElementById("live-scene-label");
        const summary = document.getElementById("live-summary");
        const metrics = document.getElementById("live-metrics");
        const events = document.getElementById("live-events");
        const preview = document.getElementById("live-preview");
        const previewCaption = document.getElementById("preview-caption");
        const startButton = document.getElementById("start-workspace");
        const recordButton = document.getElementById("record-workspace");
        const validateButton = document.getElementById("validate-workspace");
        const stopButton = document.getElementById("stop-workspace");
        const integrationSummary = document.getElementById("integration-summary");
        const integrationPath = document.getElementById("integration-path");
        const integrationTargets = document.getElementById("integration-targets");
        const addIntegrationButton = document.getElementById("add-integration");
        const saveIntegrationsButton = document.getElementById("save-integrations");
        const canRecord = {json.dumps(workspace["source_mode"] != "replay")};
        const integrationSources = ["trigger", "event", "status", "session_summary"];
        const integrationTypes = ["log", "stdout", "file_append", "webhook", "mqtt_publish"];
        const webhookMethods = ["POST", "PATCH", "PUT", "DELETE"];

        function escapeHtml(value) {{
          return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;");
        }}

        function optionMarkup(options, selectedValue) {{
          return options
            .map((option) => `<option value="${{option}}"${{option === selectedValue ? " selected" : ""}}>${{option}}</option>`)
            .join("");
        }}

        function emptyIntegrationTarget() {{
          return {{
            id: `integration-${{Date.now()}}`,
            type: "log",
            source: "trigger",
            enabled: true,
            destination: "integration_dispatch",
            method: "POST",
            mqtt_host: "",
            mqtt_port: 1883,
            mqtt_topic: "",
            event_types: [],
            trigger_ids: [],
            interval_seconds: null,
          }};
        }}

        function integrationCardMarkup(target) {{
          const triggerIds = (target.trigger_ids || []).join(", ");
          const eventTypes = (target.event_types || []).join(", ");
          return `
            <article class="integration-card">
              <div class="integration-card-header">
                <strong>${{escapeHtml(target.id || "New integration")}}</strong>
                <button type="button" class="secondary-button compact-button" data-action="remove-integration">Remove</button>
              </div>
              <div class="editor-grid">
                <label class="editor-field">
                  <span>ID</span>
                  <input type="text" data-field="id" value="${{escapeHtml(target.id || "")}}">
                </label>
                <label class="editor-field">
                  <span>Source</span>
                  <select data-field="source">${{optionMarkup(integrationSources, target.source || "trigger")}}</select>
                </label>
                <label class="editor-field">
                  <span>Type</span>
                  <select data-field="type">${{optionMarkup(integrationTypes, target.type || "log")}}</select>
                </label>
                <label class="editor-field checkbox-field">
                  <span>Enabled</span>
                  <input type="checkbox" data-field="enabled"${{target.enabled === false ? "" : " checked"}}>
                </label>
                <label class="editor-field" data-group="destination">
                  <span data-role="destination-label">Destination</span>
                  <input type="text" data-field="destination" value="${{escapeHtml(target.destination || "")}}">
                </label>
                <label class="editor-field" data-group="method">
                  <span>Method</span>
                  <select data-field="method">${{optionMarkup(webhookMethods, target.method || "POST")}}</select>
                </label>
                <label class="editor-field" data-group="mqtt-host">
                  <span>MQTT host</span>
                  <input type="text" data-field="mqtt_host" value="${{escapeHtml(target.mqtt_host || "")}}">
                </label>
                <label class="editor-field" data-group="mqtt-topic">
                  <span>MQTT topic</span>
                  <input type="text" data-field="mqtt_topic" value="${{escapeHtml(target.mqtt_topic || "")}}">
                </label>
                <label class="editor-field" data-group="mqtt-port">
                  <span>MQTT port</span>
                  <input type="number" data-field="mqtt_port" min="1" value="${{escapeHtml(target.mqtt_port ?? 1883)}}">
                </label>
                <label class="editor-field" data-group="event-types">
                  <span>Event types</span>
                  <input type="text" data-field="event_types" value="${{escapeHtml(eventTypes)}}" placeholder="focus_started, distraction_started">
                </label>
                <label class="editor-field" data-group="trigger-ids">
                  <span>Trigger IDs</span>
                  <input type="text" data-field="trigger_ids" value="${{escapeHtml(triggerIds)}}" placeholder="focus-sustained">
                </label>
                <label class="editor-field" data-group="interval">
                  <span>Interval seconds</span>
                  <input type="number" data-field="interval_seconds" min="0.1" step="0.1" value="${{escapeHtml(target.interval_seconds ?? "")}}">
                </label>
              </div>
            </article>
          `;
        }}

        function syncIntegrationCard(card) {{
          const source = card.querySelector('[data-field="source"]').value;
          const type = card.querySelector('[data-field="type"]').value;
          const destinationGroup = card.querySelector('[data-group="destination"]');
          const destinationLabel = card.querySelector('[data-role="destination-label"]');
          const methodGroup = card.querySelector('[data-group="method"]');
          const mqttHostGroup = card.querySelector('[data-group="mqtt-host"]');
          const mqttTopicGroup = card.querySelector('[data-group="mqtt-topic"]');
          const mqttPortGroup = card.querySelector('[data-group="mqtt-port"]');
          const eventTypesGroup = card.querySelector('[data-group="event-types"]');
          const triggerIdsGroup = card.querySelector('[data-group="trigger-ids"]');
          const intervalGroup = card.querySelector('[data-group="interval"]');

          destinationGroup.classList.toggle("is-hidden", type === "stdout" || type === "mqtt_publish");
          methodGroup.classList.toggle("is-hidden", type !== "webhook");
          mqttHostGroup.classList.toggle("is-hidden", type !== "mqtt_publish");
          mqttTopicGroup.classList.toggle("is-hidden", type !== "mqtt_publish");
          mqttPortGroup.classList.toggle("is-hidden", type !== "mqtt_publish");
          eventTypesGroup.classList.toggle("is-hidden", source !== "event");
          triggerIdsGroup.classList.toggle("is-hidden", source !== "trigger");
          intervalGroup.classList.toggle("is-hidden", source !== "status");

          if (type === "file_append") {{
            destinationLabel.textContent = "File path";
          }} else if (type === "webhook") {{
            destinationLabel.textContent = "Webhook URL";
          }} else {{
            destinationLabel.textContent = "Log event";
          }}

          const title = card.querySelector(".integration-card-header strong");
          const idField = card.querySelector('[data-field="id"]');
          title.textContent = idField.value.trim() || "New integration";
        }}

        function renderIntegrationTargets(targets) {{
          if (!targets.length) {{
            integrationTargets.innerHTML = '<p class="editor-empty">No integration targets yet. Add one here and save to create the workspace file.</p>';
            return;
          }}
          integrationTargets.innerHTML = targets.map((target) => integrationCardMarkup(target)).join("");
          for (const card of integrationTargets.querySelectorAll(".integration-card")) {{
            syncIntegrationCard(card);
          }}
        }}

        function parseListField(value) {{
          return value
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean);
        }}

        function collectIntegrationTargets() {{
          return [...integrationTargets.querySelectorAll(".integration-card")].map((card) => {{
            const target = {{
              id: card.querySelector('[data-field="id"]').value.trim(),
              source: card.querySelector('[data-field="source"]').value,
              type: card.querySelector('[data-field="type"]').value,
              enabled: card.querySelector('[data-field="enabled"]').checked,
              destination: card.querySelector('[data-field="destination"]').value.trim(),
              method: card.querySelector('[data-field="method"]').value,
              mqtt_host: card.querySelector('[data-field="mqtt_host"]').value.trim(),
              mqtt_topic: card.querySelector('[data-field="mqtt_topic"]').value.trim(),
              mqtt_port: card.querySelector('[data-field="mqtt_port"]').value.trim(),
              event_types: parseListField(card.querySelector('[data-field="event_types"]').value),
              trigger_ids: parseListField(card.querySelector('[data-field="trigger_ids"]').value),
              interval_seconds: card.querySelector('[data-field="interval_seconds"]').value.trim(),
            }};
            if (!target.destination) {{
              delete target.destination;
            }}
            if (!target.mqtt_host) {{
              delete target.mqtt_host;
            }}
            if (!target.mqtt_topic) {{
              delete target.mqtt_topic;
            }}
            if (!target.mqtt_port) {{
              delete target.mqtt_port;
            }}
            if (!target.interval_seconds) {{
              target.interval_seconds = null;
            }}
            return target;
          }});
        }}

        async function loadIntegrations() {{
          const response = await fetch(`/api/workspaces/${{workspaceId}}/integrations`, {{ cache: "no-store" }});
          const payload = await response.json();
          if (!response.ok) {{
            integrationSummary.textContent = payload.error || "Unable to load integration targets.";
            integrationTargets.innerHTML = '<p class="editor-empty">No integration targets available.</p>';
            return;
          }}
          integrationSummary.textContent = payload.exists
            ? `Editing ${{payload.target_count}} integration target${{payload.target_count === 1 ? "" : "s"}} for this workspace.`
            : "No integrations file exists yet. Save here to create one for this workspace.";
          integrationPath.textContent = `Path: ${{payload.path}}`;
          renderIntegrationTargets(payload.targets || []);
        }}

        async function saveIntegrations() {{
          const response = await fetch(`/api/workspaces/${{workspaceId}}/integrations`, {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ targets: collectIntegrationTargets() }}),
          }});
          const payload = await response.json();
          if (!response.ok) {{
            integrationSummary.textContent = payload.error || "Unable to save integration targets.";
            return;
          }}
          integrationSummary.textContent = payload.summary;
          integrationPath.textContent = `Path: ${{payload.path}}`;
          renderIntegrationTargets(payload.targets || []);
        }}

        async function sendControl(path) {{
          const response = await fetch(path, {{ method: "POST" }});
          const payload = await response.json();
          if (!response.ok) {{
            events.innerHTML = `<li>${{payload.error || "Control request failed."}}</li>`;
            return;
          }}
          await refreshWorkspace();
        }}

        async function validateWorkspace() {{
          const response = await fetch(`/api/workspaces/${{workspaceId}}/validate`, {{ method: "POST" }});
          const payload = await response.json();
          if (!response.ok) {{
            events.innerHTML = `<li>${{payload.error || "Validation failed."}}</li>`;
            return;
          }}
          sceneLabel.textContent = "Validation complete";
          summary.textContent = payload.summary;
          metrics.textContent = payload.report;
          const checks = payload.checks || [];
          events.innerHTML = checks.length
            ? checks.map((check) => `<li>${{check.name}}: ${{check.status.toUpperCase()}} - ${{check.detail}}</li>`).join("")
            : "<li>No validation checks were returned.</li>";
        }}

        async function refreshWorkspace() {{
          const response = await fetch(`/api/workspaces/${{workspaceId}}/live`, {{ cache: "no-store" }});
          const payload = await response.json();
          if (!payload.active) {{
            sceneLabel.textContent = "Awaiting session";
            summary.textContent = "Start a run from the CLI for this space to stream live state into the browser.";
            metrics.textContent = "No active metrics yet.";
            events.innerHTML = "<li>No live session yet.</li>";
            previewCaption.textContent = "Open a live run for this space to populate the browser preview.";
            startButton.disabled = false;
            recordButton.disabled = !canRecord;
            stopButton.disabled = true;
            return;
          }}

          sceneLabel.textContent = payload.scene_label || "Running";
          summary.textContent = payload.explanation || "Live explanation unavailable.";
          const details = payload.metrics || {{}};
          metrics.textContent = `FPS ${{
            Number(details.fps || 0).toFixed(2)
          }} • Avg ${{
            Number(details.average_inference_ms || 0).toFixed(1)
          }}ms • Stability ${{
            Number(details.stability_score || 0).toFixed(2)
          }}`;
          const items = [...(payload.recent_events || []), ...(payload.warnings || [])];
          events.innerHTML = items.length
            ? items.map((item) => `<li>${{item}}</li>`).join("")
            : "<li>No recent events or warnings.</li>";
          preview.src = `/api/workspaces/${{workspaceId}}/preview?ts=${{Date.now()}}`;
          previewCaption.textContent = "Live preview updates automatically while the session is running.";
          startButton.disabled = true;
          recordButton.disabled = true;
          stopButton.disabled = false;
        }}

        startButton.addEventListener("click", () => sendControl(`/api/workspaces/${{workspaceId}}/start`));
        recordButton.addEventListener("click", () => sendControl(`/api/workspaces/${{workspaceId}}/start-recording`));
        validateButton.addEventListener("click", validateWorkspace);
        stopButton.addEventListener("click", () => sendControl("/api/runtime/stop"));
        addIntegrationButton.addEventListener("click", () => {{
          const existing = integrationTargets.querySelectorAll(".integration-card");
          const nextTargets = existing.length ? collectIntegrationTargets() : [];
          nextTargets.push(emptyIntegrationTarget());
          renderIntegrationTargets(nextTargets);
        }});
        saveIntegrationsButton.addEventListener("click", saveIntegrations);
        integrationTargets.addEventListener("click", (event) => {{
          const actionTarget = event.target.closest("[data-action='remove-integration']");
          if (!actionTarget) {{
            return;
          }}
          const card = actionTarget.closest(".integration-card");
          if (!card) {{
            return;
          }}
          card.remove();
          if (!integrationTargets.querySelector(".integration-card")) {{
            integrationTargets.innerHTML = '<p class="editor-empty">No integration targets yet. Add one here and save to create the workspace file.</p>';
          }}
        }});
        integrationTargets.addEventListener("change", (event) => {{
          const card = event.target.closest(".integration-card");
          if (card) {{
            syncIntegrationCard(card);
          }}
        }});
        integrationTargets.addEventListener("input", (event) => {{
          const card = event.target.closest(".integration-card");
          if (card && event.target.matches('[data-field="id"]')) {{
            syncIntegrationCard(card);
          }}
        }});
        refreshWorkspace();
        loadIntegrations();
        window.setInterval(refreshWorkspace, 1500);
      </script>
    </main>
    """
    return _base_document(f"{workspace['name']} - Vision OS", content)


def _base_document(title: str, content: str) -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)}</title>
    <style>
      :root {{
        color-scheme: light;
        --ink: #122033;
        --muted: #55657f;
        --paper: #f5f1e7;
        --panel: rgba(255, 252, 246, 0.82);
        --line: rgba(18, 32, 51, 0.12);
        --accent: #c75d2c;
        --accent-soft: rgba(199, 93, 44, 0.12);
        --shadow: 0 20px 60px rgba(18, 32, 51, 0.12);
      }}

      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        min-height: 100vh;
        font-family: "Avenir Next", "Segoe UI", sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(199, 93, 44, 0.16), transparent 28%),
          radial-gradient(circle at top right, rgba(38, 96, 142, 0.12), transparent 24%),
          linear-gradient(180deg, #fbf6ea 0%, #f2ede0 100%);
      }}

      a {{ color: inherit; text-decoration: none; }}

      code {{
        display: inline-block;
        padding: 0.18rem 0.4rem;
        border-radius: 999px;
        background: rgba(18, 32, 51, 0.06);
        font-family: "SFMono-Regular", "Menlo", monospace;
        font-size: 0.83rem;
      }}

      .page-shell {{
        width: min(1180px, calc(100vw - 2rem));
        margin: 0 auto;
        padding: 2rem 0 3rem;
      }}

      .hero-panel,
      .card {{
        border: 1px solid var(--line);
        border-radius: 28px;
        background: var(--panel);
        backdrop-filter: blur(12px);
        box-shadow: var(--shadow);
      }}

      .hero-panel {{
        display: grid;
        gap: 1.5rem;
        grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.8fr);
        padding: 1.75rem;
      }}

      .hero-panel h1,
      .card h2,
      .card h3 {{
        margin: 0;
        font-family: "Iowan Old Style", "Georgia", serif;
        letter-spacing: -0.02em;
      }}

      .hero-panel h1 {{ font-size: clamp(2.5rem, 4vw, 4rem); }}
      .lede {{ margin: 0.85rem 0 0; color: var(--muted); font-size: 1.05rem; line-height: 1.55; }}
      .eyebrow,
      .card-kicker {{
        margin: 0 0 0.55rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-size: 0.78rem;
        color: var(--accent);
      }}

      .hero-stats {{
        display: grid;
        gap: 1rem;
        align-content: start;
      }}

      .stat-card {{
        padding: 1rem 1.1rem;
        border-radius: 20px;
        background: rgba(255, 255, 255, 0.52);
        border: 1px solid var(--line);
      }}

      .stat-label {{ display: block; color: var(--muted); font-size: 0.86rem; }}
      .stat-card strong {{ font-size: 1.8rem; }}

      .grid-section {{ margin-top: 1.4rem; }}
      .section-header {{ margin-bottom: 0.9rem; }}
      .section-header h2 {{ margin: 0; font-family: "Iowan Old Style", "Georgia", serif; font-size: 1.7rem; }}

      .card-grid {{
        display: grid;
        gap: 1rem;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      }}

      .card-grid-four {{
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      }}

      .card {{
        padding: 1.15rem;
        min-height: 180px;
      }}

      .workspace-card,
      .session-card {{
        transition: transform 140ms ease, border-color 140ms ease;
      }}

      .workspace-card:hover,
      .session-card:hover {{
        transform: translateY(-2px);
        border-color: rgba(199, 93, 44, 0.38);
      }}

      .status-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.55rem;
        color: var(--muted);
        font-size: 0.92rem;
      }}

      .empty-card {{
        border-style: dashed;
        background: rgba(255, 255, 255, 0.45);
      }}

      .primary-link {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-top: 1rem;
        padding: 0.85rem 1.15rem;
        border-radius: 999px;
        background: var(--accent);
        color: #fff9f4;
        font-weight: 600;
      }}

      .workspace-shell {{
        display: grid;
        gap: 1rem;
        grid-template-columns: minmax(0, 1fr) minmax(300px, 0.9fr);
        margin-top: 1.25rem;
      }}

      .workspace-preview,
      .workspace-status,
      .workspace-events,
      .workspace-tabs,
      .workspace-integrations {{
        min-height: 240px;
      }}

      .workspace-integrations {{
        grid-column: 1 / -1;
      }}

      .preview-frame {{
        width: 100%;
        aspect-ratio: 16 / 9;
        object-fit: cover;
        border-radius: 18px;
        background: rgba(18, 32, 51, 0.08);
        border: 1px solid var(--line);
      }}

      .workspace-controls {{
        display: flex;
        gap: 0.75rem;
        margin: 0.25rem 0 1rem;
      }}

      button {{
        border: 0;
        border-radius: 999px;
        padding: 0.8rem 1rem;
        background: var(--accent);
        color: #fff9f4;
        font-weight: 600;
        cursor: pointer;
      }}

      button.secondary-button {{
        background: rgba(18, 32, 51, 0.14);
        color: var(--ink);
      }}

      .compact-button {{
        padding: 0.45rem 0.75rem;
        font-size: 0.82rem;
      }}

      button:disabled {{
        cursor: not-allowed;
        opacity: 0.55;
      }}

      .tab-list {{
        display: grid;
        gap: 0.75rem;
        padding: 0;
        margin: 1rem 0 0;
        list-style: none;
      }}

      .tab-list li {{
        padding: 0.85rem 1rem;
        border-radius: 16px;
        background: var(--accent-soft);
      }}

      .editor-note,
      .editor-empty {{
        color: var(--muted);
      }}

      .editor-stack {{
        display: grid;
        gap: 0.85rem;
        margin-top: 0.85rem;
      }}

      .integration-card {{
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 1rem;
        background: rgba(255, 255, 255, 0.48);
      }}

      .integration-card-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        margin-bottom: 0.85rem;
      }}

      .editor-grid {{
        display: grid;
        gap: 0.75rem;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      }}

      .editor-field {{
        display: grid;
        gap: 0.35rem;
        font-size: 0.9rem;
      }}

      .editor-field span {{
        color: var(--muted);
      }}

      .editor-field input,
      .editor-field select {{
        width: 100%;
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 0.72rem 0.85rem;
        background: rgba(255, 255, 255, 0.88);
        color: var(--ink);
        font: inherit;
      }}

      .checkbox-field {{
        align-content: end;
      }}

      .checkbox-field input {{
        width: 1.1rem;
        height: 1.1rem;
        padding: 0;
      }}

      .is-hidden {{
        display: none;
      }}

      @media (max-width: 860px) {{
        .hero-panel,
        .workspace-shell {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
  </head>
  <body>
    {content}
  </body>
</html>"""


def serve_launchpad(app: LaunchpadApp, *, host: str, port: int, open_browser: bool) -> int:
    """Run the local browser shell until the operator stops it."""
    browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    url = f"http://{browser_host}:{port}/"
    with make_server(host, port, app) as server:
        print(f"Vision OS browser app running at {url}")
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0
