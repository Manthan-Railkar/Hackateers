"""
Tests for Dashboard UI endpoints (/ and /api/metrics).
"""

import pytest
import urllib.request
import json
from browser_optimizer.dashboard.server import start_dashboard_server


TEST_PORT = 8059


@pytest.fixture(scope="module", autouse=True)
def dashboard_server_fixture():
    """Ensure the dashboard HTTP server is running on isolated port for tests."""
    server = start_dashboard_server(port=TEST_PORT)
    yield server


def test_dashboard_page_route():
    """Test that GET / returns the original dashboard HTML content."""
    url = f"http://localhost:{TEST_PORT}/"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        content = resp.read().decode("utf-8")
        assert "Browser Optimizer — Live Dashboard" in content or "Browser Optimizer" in content


def test_api_metrics_endpoint():
    """Test that GET /api/metrics returns JSON metrics payload."""
    url = f"http://localhost:{TEST_PORT}/api/metrics"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "estimated_tokens_saved" in data
        assert "estimated_cost_saved_usd" in data
        assert "active_sessions" in data
