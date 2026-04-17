"""WSGI app for the Vision OS local browser shell."""

from __future__ import annotations

import json
from html import escape
from urllib.parse import unquote

from server.launchpad import LaunchpadService


class LaunchpadApp:
    """Serve the Launchpad and workspace shell over a local browser session."""

    def __init__(self, service: LaunchpadService) -> None:
        self.service = service

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "/")
        if path == "/":
            return self._html_response(start_response, _render_launchpad(self.service.build_snapshot()))
        if path == "/api/launchpad":
            payload = json.dumps(self.service.build_snapshot(), indent=2)
            return self._json_response(start_response, payload)
        if path.startswith("/workspaces/"):
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
        <article class="card workspace-status">
          <p class="card-kicker">Ready state</p>
          <h2>{escape(status["validation_summary"] or "No validation recorded yet")}</h2>
          <p>Profile: {escape(workspace["profile_id"] or "none")} • Policy: {escape(workspace["policy_name"] or "default")}</p>
        </article>
        <article class="card workspace-tabs">
          <p class="card-kicker">Workspace navigation</p>
          <h2>Operator flow</h2>
          <ul class="tab-list">{tabs}</ul>
        </article>
      </section>
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
