"""
Browser management module using Playwright.
Handles launching, session contexts, page management, and teardown.
"""

import base64
from typing import Any, Dict, Optional, Tuple
import base64
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page
from browser_optimizer.config.settings import settings
from browser_optimizer.utils.logger import logger
from browser_optimizer.cache.db import session_state_store


class LiveScreenshotStore:
    """
    In-memory store holding the latest live screenshot, URL, title, and active action description
    per session to stream live visual updates to the Mission Control dashboard.
    """
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def update(self, session_id: str, b64: str, url: str, title: str, action: str):
        self._store[session_id] = {
            "b64": b64,
            "url": url,
            "title": title,
            "action": action
        }

    async def capture(self, page, session_id: str = "default", action: str = "Observing Page"):
        try:
            if page and hasattr(page, "screenshot") and not (hasattr(page, "is_closed") and page.is_closed()):
                screenshot_bytes = await page.screenshot(type="jpeg", quality=60)
                b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                url = getattr(page, "url", "about:blank")
                title = await page.title() if hasattr(page, "title") else ""
                self.update(session_id, b64, url, title, action)
        except Exception as e:
            logger.debug(f"Live screenshot capture omitted: {e}")

    def get(self, session_id: str = "default") -> Optional[Dict[str, Any]]:
        return self._store.get(session_id)


live_screenshot_store = LiveScreenshotStore()


class BrowserManager:
    """
    Manages the lifecycle of a Playwright browser instance and standard page contexts
    mapped by session_id to support isolated concurrent execution.
    """
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.sessions: Dict[str, Tuple[BrowserContext, Page]] = {}


    async def start(self):
        """
        Launch the Chromium instance in headless/headed mode according to settings.
        Initializes the async Playwright driver.
        """
        if self.browser is not None:
            logger.info("Browser already started or mocked.")
            return
        logger.info("Starting Browser...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=settings.HEADLESS
        )
        logger.info("Chromium Started")

    async def stop(self):
        """
        Closes active pages and contexts across all sessions, then shuts down the browser.
        """
        logger.info("Stopping Browser...")
        # Close all active sessions
        for session_id in list(self.sessions.keys()):
            await self.close_session(session_id)
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.sessions.clear()
        self.browser = None
        self.playwright = None
        logger.info("Chromium Stopped")

    async def get_page(self, session_id: str = "default") -> Page:
        """
        Retrieve the page context for the specified session_id.
        Creates a new context and page if none exists, or if the page has been closed.
        Automatically handles browser process restarts if disconnected.
        
        Returns:
            Page: Isolated Playwright page object ready for automation.
        """
        # Ensure browser is connected if real browser instance
        if self.browser is None or (hasattr(self.browser, "is_connected") and not self.browser.is_connected()):
            logger.warning("Browser instance disconnected or not started. Restarting Chromium...")
            self.browser = None
            await self.start()

        if session_id not in self.sessions or self.sessions[session_id][1].is_closed():
            logger.info(f"Initializing new isolated BrowserContext for session: {session_id}")
            
            state: Any = None
            try:
                state = session_state_store.get_state(session_id)
                if state:
                    logger.info(f"Restoring previous session state for '{session_id}'")
            except Exception as e:
                logger.warning(f"Failed to load session state for '{session_id}': {e}")

            if state:
                context = await self.browser.new_context(storage_state=state)
            else:
                context = await self.browser.new_context()
            page = await context.new_page()
            self.sessions[session_id] = (context, page)
        return self.sessions[session_id][1]

    async def navigate(self, url: str, session_id: str = "default"):
        """
        Navigate to a specific URL and wait for DOM load completion in the given session.
        Automatically creates a DOM checkpoint post-navigation.
        
        Args:
            url (str): Target web application link.
            session_id (str): Target session ID.
            
        Returns:
            Page: Loaded page object.
        """
        page = await self.get_page(session_id)
        await page.goto(url, timeout=settings.BROWSER_TIMEOUT, wait_until="domcontentloaded")
        await self.save_session_state(session_id)
        await live_screenshot_store.capture(page, session_id, f"Navigated to {url}")
        
        # Automatic checkpointing hook post-navigation
        try:
            from browser_optimizer.recovery.manager import recovery_manager
            await recovery_manager.create_checkpoint(page, session_id, action_trigger="navigate")
        except Exception as e:
            logger.debug(f"Automatic navigation checkpoint skipped: {e}")
            
        return page

    async def save_session_state(self, session_id: str):
        """
        Save the browser context storage state for the session to the database.
        """
        if session_id in self.sessions:
            context, page = self.sessions[session_id]
            if not page.is_closed():
                try:
                    state = await context.storage_state()
                    session_state_store.save_state(session_id, state)
                    logger.info(f"Saved session state for '{session_id}' to database.")
                except Exception as e:
                    logger.warning(f"Failed to save session state for '{session_id}': {e}")

    async def close_session(self, session_id: str):
        """
        Close page and BrowserContext for a specific session.
        """
        if session_id in self.sessions:
            await self.save_session_state(session_id)
            logger.info(f"Closing BrowserContext for session: {session_id}")
            context, page = self.sessions[session_id]
            try:
                if not page.is_closed():
                    await page.close()
                await context.close()
            except Exception as e:
                logger.warning(f"Error closing session {session_id}: {e}")
            self.sessions.pop(session_id, None)


# Shared manager instance
manager = BrowserManager()