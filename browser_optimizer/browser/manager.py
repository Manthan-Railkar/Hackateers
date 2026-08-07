import asyncio
from typing import Dict, Optional, Tuple
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from browser_optimizer.cache.db import load_session_state, save_session_state, init_db
from browser_optimizer.config.settings import get_settings
from browser_optimizer.utils.logger import logger


class BrowserManager:
    """
    Async Playwright Browser Manager.
    Manages browser context lifecycles, multi-session state isolation,
    and automatic session persistence using SQLite storage.
    """
    _instance: Optional["BrowserManager"] = None

    def __init__(self):
        self.settings = get_settings()
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.sessions: Dict[str, Tuple[BrowserContext, Page]] = {}
        self._lock = asyncio.Lock()
        init_db()

    async def _ensure_browser(self) -> None:
        """
        Ensures Playwright driver and Chromium browser instance are active.
        """
        async with self._lock:
            if not self.playwright:
                logger.info("Starting Playwright driver...")
                self.playwright = await async_playwright().start()
            if not self.browser or not self.browser.is_connected():
                logger.info(f"Launching Chromium headless={self.settings.HEADLESS}...")
                self.browser = await self.playwright.chromium.launch(
                    headless=self.settings.HEADLESS
                )
                logger.info("Chromium browser instance launched successfully.")

    async def get_page(self, session_id: str = "default") -> Page:
        """
        Retrieves or creates a Page instance for the specified session_id.
        Restores storage state from SQLite if available.
        """
        await self._ensure_browser()

        async with self._lock:
            if session_id in self.sessions:
                context, page = self.sessions[session_id]
                if not page.is_closed():
                    return page
                else:
                    logger.warning(f"Page for session '{session_id}' was closed. Re-creating...")

            # Load persistent session state from SQLite if exists
            stored_state = load_session_state(session_id)
            if stored_state:
                logger.info(f"Restoring persistent session state for '{session_id}' from SQLite.")
                context = await self.browser.new_context(storage_state=stored_state)
            else:
                logger.info(f"Creating fresh BrowserContext for session '{session_id}'.")
                context = await self.browser.new_context()

            page = await context.new_page()
            self.sessions[session_id] = (context, page)
            return page

    async def navigate(self, url: str, session_id: str = "default") -> Page:
        """
        Navigates the page for the given session_id to the target URL,
        waits for DOM content loaded, and persists updated session state to SQLite.
        """
        page = await self.get_page(session_id)
        logger.info(f"Session '{session_id}' navigating to URL: '{url}'")
        
        try:
            await page.goto(
                url,
                timeout=self.settings.BROWSER_TIMEOUT,
                wait_until="domcontentloaded"
            )
        except Exception as e:
            logger.error(f"Navigation failed for session '{session_id}' to '{url}': {e}")
            raise

        # Auto-persist session cookies / storage state after navigation
        await self.save_session(session_id)
        return page

    async def save_session(self, session_id: str = "default") -> None:
        """
        Extracts storage state (cookies, localStorage) from active context and saves to SQLite.
        """
        if session_id in self.sessions:
            context, _ = self.sessions[session_id]
            try:
                storage_state = await context.storage_state()
                save_session_state(session_id, storage_state)
                logger.debug(f"Saved active storage state for session '{session_id}'.")
            except Exception as e:
                logger.error(f"Failed to extract/save storage state for session '{session_id}': {e}")

    async def close_session(self, session_id: str = "default") -> None:
        """
        Closes context and page for a specific session_id.
        """
        async with self._lock:
            if session_id in self.sessions:
                context, page = self.sessions.pop(session_id)
                try:
                    if not page.is_closed():
                        await page.close()
                    await context.close()
                    logger.info(f"Closed session '{session_id}'.")
                except Exception as e:
                    logger.error(f"Error closing session '{session_id}': {e}")

    async def stop(self) -> None:
        """
        Shuts down all active browser sessions, closes Chromium browser instance,
        and terminates Playwright driver cleanly.
        """
        async with self._lock:
            logger.info("Shutting down BrowserManager...")
            for session_id in list(self.sessions.keys()):
                context, page = self.sessions.pop(session_id)
                try:
                    if not page.is_closed():
                        await page.close()
                    await context.close()
                except Exception as e:
                    logger.error(f"Error closing session '{session_id}' context: {e}")

            if self.browser:
                try:
                    await self.browser.close()
                except Exception as e:
                    logger.error(f"Error closing browser: {e}")
                self.browser = None

            if self.playwright:
                try:
                    await self.playwright.stop()
                except Exception as e:
                    logger.error(f"Error stopping playwright: {e}")
                self.playwright = None

            logger.info("BrowserManager stopped successfully.")


_global_manager: Optional[BrowserManager] = None


def get_browser_manager() -> BrowserManager:
    """
    Returns singleton instance of BrowserManager.
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = BrowserManager()
    return _global_manager
