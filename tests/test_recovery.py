import asyncio
import time
import pytest
from bs4 import BeautifulSoup
from playwright.async_api import Page, Error as PlaywrightError

from browser_optimizer.config.settings import settings
from browser_optimizer.schemas.schemas import DOMCheckpoint, RecoveryConfidenceResult
from browser_optimizer.cache.db import dom_checkpoint_db
from browser_optimizer.recovery.manager import recovery_manager


@pytest.fixture
def clean_db():
    dom_checkpoint_db.delete_session_checkpoints("test_session")
    yield
    dom_checkpoint_db.delete_session_checkpoints("test_session")


def test_dom_hashing_determinism():
    """Verify DOM hash strips dynamic scripts, react IDs, csrf tokens, and whitespace."""
    html_1 = """
    <html>
        <head>
            <script>var csrf = 'abc12345';</script>
            <style>.test { color: red; }</style>
        </head>
        <body data-reactid="12">
            <h1 nonce="random123">Welcome User</h1>
            <div csrf-token="token-xyz">
                <p>Dashboard Content</p>
            </div>
        </body>
    </html>
    """
    html_2 = """
    <html>
        <head>
            <script>var csrf = 'different_token_999';</script>
            <style>.test { color: blue; }</style>
        </head>
        <body data-reactid="99">
            <h1 nonce="nonce_different_456">Welcome User</h1>
            <div csrf-token="token-different">
                <p>Dashboard Content</p>
            </div>
        </body>
    </html>
    """

    hash_1 = recovery_manager.compute_dom_hash(html_1)
    hash_2 = recovery_manager.compute_dom_hash(html_2)

    assert hash_1 != ""
    assert hash_2 != ""
    assert hash_1 == hash_2, "DOM hashes should match when static semantic content is identical."


def test_failure_categorization():
    """Verify failure categorization maps exceptions to recoverable categories."""
    e_browser = PlaywrightError("Target page, context or browser has been closed")
    is_rec, cat, msg = recovery_manager.detect_failure(e_browser)
    assert is_rec is True
    assert cat == "BROWSER_CLOSED"

    e_ws = Exception("WebSocket connection to ws://localhost:8765 failed")
    is_rec, cat, msg = recovery_manager.detect_failure(e_ws)
    assert is_rec is True
    assert cat == "WEBSOCKET_DISCONNECT"

    e_timeout = Exception("Navigation timeout of 30000ms exceeded")
    is_rec, cat, msg = recovery_manager.detect_failure(e_timeout)
    assert is_rec is True
    assert cat == "NAVIGATION_TIMEOUT"


def test_database_persistence_and_pruning(clean_db):
    """Verify storing checkpoints in SQLite dom_checkpoints table and retention pruning."""
    session_id = "test_session"

    # Insert 25 checkpoints (max is 20)
    for i in range(25):
        checkpoint_data = {
            "session_id": session_id,
            "url": f"https://example.com/page-{i}",
            "page_title": f"Page {i}",
            "compressed_dom": {"ui": [{"tag": "button", "text": f"Btn {i}"}]},
            "dom_hash": f"hash_{i}",
            "scroll_x": 0,
            "scroll_y": 100 * i,
            "viewport_width": 1280,
            "viewport_height": 720,
            "timestamp": time.time() + i,
            "checkpoint_version": "1.0",
            "metadata": {"step": i}
        }
        dom_checkpoint_db.save_checkpoint(checkpoint_data, max_checkpoints=20, retention_days=7)

    # Check latest
    latest = dom_checkpoint_db.get_latest_checkpoint(session_id)
    assert latest is not None
    assert latest["url"] == "https://example.com/page-24"
    assert latest["scroll_y"] == 2400

    # Verify max_checkpoints pruning kept only 20
    all_checkpoints = dom_checkpoint_db.list_checkpoints(session_id, limit=50)
    assert len(all_checkpoints) == 20
    assert all_checkpoints[0]["url"] == "https://example.com/page-24"
    assert all_checkpoints[-1]["url"] == "https://example.com/page-5"


def test_recovery_confidence_scoring():
    """Verify confidence calculation for exact match, partial match, and mismatch."""
    stored = DOMCheckpoint(
        session_id="test_session",
        timestamp=time.time(),
        url="https://example.com/dashboard",
        page_title="Dashboard",
        compressed_dom={
            "ui": [
                {"tag": "input", "id": "search", "name": "q", "type": "text"},
                {"tag": "button", "id": "submit-btn", "text": "Search"},
                {"tag": "a", "href": "/logout", "text": "Logout"}
            ]
        },
        dom_hash="exact_hash_123"
    )

    # 1. Exact match (Score 1.0)
    result_exact = recovery_manager.calculate_recovery_confidence(
        stored,
        live_url="https://example.com/dashboard",
        live_title="Dashboard",
        live_dom_hash="exact_hash_123",
        live_ui=stored.compressed_dom["ui"]
    )
    assert result_exact.confidence == 1.0
    assert result_exact.status == "EXACT_MATCH"
    assert result_exact.can_auto_resume is True

    # 2. Structural shift / Partial match
    result_partial = recovery_manager.calculate_recovery_confidence(
        stored,
        live_url="https://example.com/dashboard",
        live_title="Dashboard - Updates",
        live_dom_hash="different_hash_999",
        live_ui=[
            {"tag": "input", "id": "search", "name": "q", "type": "text"},
            {"tag": "button", "id": "submit-btn", "text": "Search"}
        ]
    )
    assert result_partial.confidence >= 0.70
    assert result_partial.can_auto_resume is True

    # 3. URL mismatch
    result_mismatch = recovery_manager.calculate_recovery_confidence(
        stored,
        live_url="https://example.com/error-page",
        live_title="404 Not Found",
        live_dom_hash="error_hash_000",
        live_ui=[]
    )
    assert result_mismatch.confidence < 0.40
    assert result_mismatch.status == "MISMATCH"
    assert result_mismatch.can_auto_resume is False


@pytest.mark.asyncio
async def test_checkpoint_creation_and_deduplication(clean_db):
    """Test creating checkpoint skips when DOM hash and URL are unchanged."""
    session_id = "test_session"

    class MockLocator:
        async def aria_snapshot(self):
            return "heading 'Test'"

    class MockPage:
        is_closed = lambda self: False
        url = "https://example.com/test"

        async def title(self):
            return "Test Title"

        async def content(self):
            return "<html><body><input id='search-input'/><button id='btn'>Submit</button></body></html>"

        def locator(self, selector):
            return MockLocator()

        async def evaluate(self, script):
            if "scrollX" in script:
                return {"x": 0, "y": 150, "w": 1280, "h": 720}
            return "#search-input"

    page = MockPage()

    # First checkpoint
    cp1 = await recovery_manager.create_checkpoint(page, session_id=session_id, action_trigger="test")
    assert cp1 is not None
    assert cp1.url == "https://example.com/test"
    assert cp1.scroll_y == 150

    # Second checkpoint on identical state should be skipped
    cp2 = await recovery_manager.create_checkpoint(page, session_id=session_id, action_trigger="test")
    assert cp2 is None, "Identical page state should skip checkpoint creation."


@pytest.mark.asyncio
async def test_browser_crash_recovery_flow(clean_db):
    """Simulate browser process disconnect and verify restore_checkpoint restores context and re-navigates."""
    session_id = "test_session"

    # Pre-populate database with checkpoint
    checkpoint_data = {
        "session_id": session_id,
        "url": "https://example.com/login",
        "page_title": "Login Page",
        "compressed_dom": {
            "title": "Login Page",
            "ui": [
                {"tag": "input", "id": "username", "type": "text"},
                {"tag": "button", "id": "login-btn", "text": "Submit"}
            ]
        },
        "dom_hash": "login_dom_hash_123",
        "scroll_x": 0,
        "scroll_y": 50,
        "timestamp": time.time()
    }
    dom_checkpoint_db.save_checkpoint(checkpoint_data)

    class MockLocator:
        async def aria_snapshot(self):
            return "heading 'Login'"

    class MockPage:
        def __init__(self):
            self.url = "https://example.com/login"
            self.scrolled_to = None

        def is_closed(self):
            return False

        async def title(self):
            return "Login Page"

        async def content(self):
            return "<html><body><input id='username'/><button id='login-btn'>Submit</button></body></html>"

        def locator(self, selector):
            return MockLocator()

        async def goto(self, url, timeout=None, wait_until=None):
            self.url = url

        async def evaluate(self, script):
            if "scrollTo" in script:
                self.scrolled_to = script
            return None

    class MockBrowserManager:
        def __init__(self):
            self.mock_page = MockPage()

        async def get_page(self, session_id: str):
            return self.mock_page

        async def save_session_state(self, session_id: str):
            pass

    mock_bm = MockBrowserManager()
    recovery_report = await recovery_manager.restore_checkpoint(session_id=session_id, browser_manager=mock_bm)

    assert recovery_report["success"] is True
    assert recovery_report["recovered"] is True
    assert recovery_report["auto_resumed"] is True
    assert recovery_report["url"] == "https://example.com/login"
