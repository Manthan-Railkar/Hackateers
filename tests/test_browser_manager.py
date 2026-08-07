import pytest
from browser_optimizer.browser.manager import BrowserManager


@pytest.mark.asyncio
async def test_browser_manager_lifecycle():
    """Verify BrowserManager initialization, page navigation, and shutdown."""
    manager = BrowserManager()
    try:
        # Navigate test session
        page = await manager.navigate("https://example.com", session_id="test_suite_session")
        assert page is not None
        title = await page.title()
        assert "Example" in title
        
        # Verify page reuse
        same_page = await manager.get_page("test_suite_session")
        assert same_page is page
        
        # Close specific session
        await manager.close_session("test_suite_session")
        assert "test_suite_session" not in manager.sessions
    finally:
        await manager.stop()
        assert manager.browser is None
        assert manager.playwright is None


@pytest.mark.asyncio
async def test_multi_session_isolation():
    """Verify multiple browser sessions run with isolated contexts."""
    manager = BrowserManager()
    try:
        page_a = await manager.get_page("session_a")
        page_b = await manager.get_page("session_b")
        
        assert page_a is not page_b
        assert page_a.context is not page_b.context
        assert len(manager.sessions) == 2
    finally:
        await manager.stop()
