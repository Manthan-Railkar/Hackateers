"""
Lightweight dashboard HTTP server using Python's built-in http.server.
Serves the dashboard UI and exposes a JSON API for live metrics polling.
Runs on port 8050 alongside the MCP stdio server.
"""

import json
import threading
import webbrowser
from typing import Optional, Dict, Any
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from browser_optimizer.metrics.metrics import metrics
from browser_optimizer.cache.db import macro_store
from browser_optimizer.utils.logger import logger
from browser_optimizer.config.settings import settings


DASHBOARD_DIR = Path(__file__).parent
DASHBOARD_PORT = settings.DASHBOARD_PORT


class DashboardHandler(SimpleHTTPRequestHandler):
    """
    Custom request handler that serves the dashboard HTML and a JSON metrics API.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/api/metrics":
            self._serve_metrics()
        elif self.path.startswith("/api/replay"):
            self._serve_replay()
        elif self.path.startswith("/api/telemetry"):
            self._serve_telemetry()
        elif self.path.startswith("/api/screenshot"):
            self._serve_screenshot()
        elif self.path in ["/", "/mission-control", "/mission_control.html"]:
            self._serve_mission_control()
        elif self.path in ["/classic", "/classic.html", "/index.html"]:
            self._serve_dashboard()
        else:
            super().do_GET()

    def _serve_metrics(self):
        """Return live metrics + macro stats as JSON."""
        stats = metrics.get_stats()

        # Enrich with macro data
        all_macros = macro_store.list_macros()
        macro_summary = []
        for m in all_macros:
            macro_summary.append({
                "id": m["id"],
                "name": m["name"],
                "page_type": m["page_type"],
                "confidence": m["confidence"],
                "success_count": m["success_count"],
                "fail_count": m["fail_count"],
                "steps": len(m.get("sequence", []))
            })

        stats["macros"] = macro_summary
        stats["macro_count"] = len(all_macros)

        # Include list of active session IDs
        from browser_optimizer.browser.manager import manager
        active_ids = list(manager.sessions.keys())
        if "default" not in active_ids:
            active_ids.append("default")
        stats["active_sessions"] = active_ids

        # Estimated cost savings (rough: $0.002 per 1K tokens, ~4 chars per token)
        tokens_saved = stats.get("bytes_saved_total", 0) / 4
        stats["estimated_tokens_saved"] = int(tokens_saved)
        stats["estimated_cost_saved_usd"] = round(tokens_saved / 1000 * 0.002, 4)

        body = json.dumps(stats).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_replay(self):
        """Return the session replay events as JSON."""
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        session_id = params.get("session_id", ["default"])[0]

        from browser_optimizer.cache.db import session_replay_store
        replay_events = session_replay_store.get_replay(session_id)

        body = json.dumps(replay_events).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_telemetry(self):
        """Return enriched real-time Mission Control telemetry data."""
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        session_id = params.get("session_id", ["default"])[0]

        stats = metrics.get_stats()
        from browser_optimizer.cache.db import session_replay_store, macro_store
        from browser_optimizer.browser.manager import manager

        replay_events = session_replay_store.get_replay(session_id)
        all_macros = macro_store.list_macros()

        # Infer current active module and workflow stage from recent events
        active_module = "Semantic Cache"
        workflow_stage = "Search"
        if replay_events:
            last_event = replay_events[-1]
            action = last_event.get("action_taken", "").lower()
            ptype = (last_event.get("page_classification") or "").lower()
            outcome = (last_event.get("outcome") or "").lower()

            if "login" in ptype:
                workflow_stage = "Login"
            elif "product" in ptype:
                workflow_stage = "Product"
            elif "cart" in ptype:
                workflow_stage = "Cart"
            elif "checkout" in ptype or "payment" in ptype:
                workflow_stage = "Checkout"
            else:
                workflow_stage = "Search"

            if "extract_context" in action:
                active_module = "Context Extraction Engine" if "miss" in outcome else "Semantic Cache"
            elif "replay" in action or "macro" in action:
                active_module = "Rule Engine"
            elif "click" in action or "type" in action or "execute" in action:
                active_module = "Playwright Adapter"

        tokens_saved = int(stats.get("bytes_saved_total", 0) / 4)
        cost_saved = round(tokens_saved / 1000 * 0.002, 4)

        telemetry = {
            "session_id": session_id,
            "metrics": stats,
            "tokens_saved": tokens_saved,
            "cost_saved_usd": cost_saved,
            "replay_events": replay_events,
            "active_module": active_module,
            "workflow_stage": workflow_stage,
            "macro_count": len(all_macros),
            "macros": all_macros,
            "active_sessions": list(manager.sessions.keys()) or ["default"]
        }

        body = json.dumps(telemetry).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_screenshot(self):
        """Serve live base64 screenshot or status JSON for the active session."""
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            session_id = params.get("session_id", ["default"])[0]

            from browser_optimizer.browser.manager import live_screenshot_store, manager

            data = live_screenshot_store.get(session_id)
            if not data and hasattr(live_screenshot_store, "_store") and live_screenshot_store._store:
                try:
                    data = list(live_screenshot_store._store.values())[-1]
                except Exception:
                    data = None

            if data:
                payload = {
                    "session_id": session_id,
                    "url": data.get("url", "about:blank"),
                    "title": data.get("title", "Active Page"),
                    "action": data.get("action", "Live Browser Automation Active"),
                    "screenshot_b64": data.get("b64"),
                    "has_live_browser": True
                }
            else:
                has_browser = False
                try:
                    has_browser = session_id in manager.sessions
                except Exception:
                    pass
                payload = {
                    "session_id": session_id,
                    "url": "https://example.com/demo",
                    "title": "Playwright Automation Active",
                    "action": "Awaiting browser interaction command...",
                    "screenshot_b64": None,
                    "has_live_browser": has_browser
                }

            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.warning(f"Error in _serve_screenshot: {e}")
            err_payload = json.dumps({"session_id": "default", "has_live_browser": False, "error": str(e)}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(err_payload)))
            self.end_headers()
            self.wfile.write(err_payload)

    def _serve_mission_control(self):
        """Serve the mission_control.html file."""
        mc_path = DASHBOARD_DIR / "mission_control.html"
        if mc_path.exists():
            content = mc_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self._serve_dashboard()

    def _serve_dashboard(self):
        """Serve the index.html dashboard file."""

        index_path = DASHBOARD_DIR / "index.html"
        if index_path.exists():
            content = index_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, "Dashboard not found")

    def log_message(self, format, *args):
        """Suppress default HTTP logs to avoid cluttering MCP stdio."""
        pass


def start_dashboard_server(port: Optional[int] = None):
    """Launch the dashboard HTTP server in a background daemon thread."""
    target_port = port or DASHBOARD_PORT
    try:
        class ReusableHTTPServer(HTTPServer):
            allow_reuse_address = True

        server = ReusableHTTPServer(("0.0.0.0", target_port), DashboardHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Dashboard server started at http://localhost:{target_port}")

        if settings.AUTO_OPEN_DASHBOARD and port is None:
            try:
                url = f"http://localhost:{target_port}/mission-control"
                logger.info(f"Automatically opening Mission Control dashboard at {url}")
                webbrowser.open(url)
            except Exception as e:
                logger.warning(f"Could not automatically open Mission Control dashboard in web browser: {e}")

        return server
    except OSError as e:
        logger.warning(f"Could not start dashboard server on port {target_port}: {e}")
        return None
