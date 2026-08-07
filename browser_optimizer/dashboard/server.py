import os
import json
from http.server import SimpleHTTPRequestHandler, HTTPServer
import threading
from browser_optimizer.metrics.metrics import metrics_tracker
from browser_optimizer.config.settings import get_settings
from browser_optimizer.utils.logger import logger

class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.path = "/index.html"
            
        if self.path == "/index.html":
            dashboard_dir = os.path.dirname(__file__)
            self.directory = dashboard_dir
            return super().do_GET()
            
        elif self.path == "/api/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            metrics = metrics_tracker.get_metrics()
            self.wfile.write(json.dumps(metrics).encode("utf-8"))
            
        elif self.path == "/api/verify_comparison":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if metrics_tracker.last_verification_data:
                self.wfile.write(json.dumps(metrics_tracker.last_verification_data).encode("utf-8"))
            else:
                self.wfile.write(json.dumps({"error": "No extraction data available yet."}).encode("utf-8"))
                
        else:
            self.send_response(404)
            self.end_headers()

def run_server_sync(port: int):
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    logger.info(f"Dashboard HTTP server running on port {port}")
    try:
        server.serve_forever()
    except Exception as e:
        logger.error(f"Dashboard server error: {e}")
        
def start_dashboard():
    settings = get_settings()
    daemon = threading.Thread(target=run_server_sync, args=(settings.DASHBOARD_PORT,), daemon=True)
    daemon.start()
