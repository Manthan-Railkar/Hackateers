"""
RecoveryManager module for DOM Checkpointing & Browser Failure Recovery.
Provides automated checkpoint creation, deterministic DOM hashing, state validation,
confidence scoring, and transparent failure recovery.
"""

import asyncio
import re
import time
from typing import Dict, Any, Optional, List, Tuple
import xxhash
from bs4 import BeautifulSoup
from playwright.async_api import Page, Error as PlaywrightError

from browser_optimizer.config.settings import settings
from browser_optimizer.utils.logger import logger
from browser_optimizer.schemas.schemas import DOMCheckpoint, RecoveryConfidenceResult
from browser_optimizer.cache.db import dom_checkpoint_db, session_state_store
from browser_optimizer.extractor.extractor import extractor
from browser_optimizer.compressor.compressor import compressor


class RecoveryManager:
    """
    Subsystem responsible for creating, persisting, validating, and restoring
    DOM checkpoints to make browser automation fault-tolerant against crashes,
    network disconnects, and timeouts.
    """

    def __init__(self):
        self._last_hashes: Dict[str, str] = {}  # session_id -> last_dom_hash
        self._last_urls: Dict[str, str] = {}    # session_id -> last_url
        self._recovery_locks: Dict[str, asyncio.Lock] = {}

    def _get_session_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._recovery_locks:
            self._recovery_locks[session_id] = asyncio.Lock()
        return self._recovery_locks[session_id]

    def compute_dom_hash(self, html_or_soup: Any) -> str:
        """
        Generate a fast (<50ms), deterministic 64-bit signature of the DOM structure.
        Strips dynamic attributes, timestamps, random tokens, script/style tags, and analytics tags.
        """
        start_time = time.time()

        if isinstance(html_or_soup, str):
            soup = BeautifulSoup(html_or_soup, "lxml")
        else:
            soup = html_or_soup

        if not soup:
            return ""

        # Make a copy for destructive normalization if soup has decompose
        clean_soup = BeautifulSoup(str(soup), "lxml")

        # Strip non-semantic & dynamic elements
        for tag in clean_soup(["script", "style", "noscript", "svg", "iframe"]):
            tag.decompose()

        # Remove dynamic attributes and comments
        for el in clean_soup.find_all(True):
            attrs_to_remove = [
                attr for attr in el.attrs
                if attr.startswith("data-react") or attr.startswith("data-v-")
                or attr.startswith("aria-aria") or attr in ("nonce", "csrf-token", "data-token", "tabindex")
            ]
            for attr in attrs_to_remove:
                del el.attrs[attr]

        # Convert to string and normalize whitespace
        clean_html = clean_soup.get_text(separator=" ", strip=True)
        clean_html = re.sub(r"\s+", " ", clean_html)

        digest = xxhash.xxh64(clean_html.encode("utf-8", errors="ignore")).hexdigest()
        elapsed_ms = (time.time() - start_time) * 1000

        if elapsed_ms > 50:
            logger.debug(f"DOM hash computation took {elapsed_ms:.2f}ms (>50ms target)")

        return digest

    async def create_checkpoint(
        self,
        page: Page,
        session_id: str = "default",
        action_trigger: str = "manual",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DOMCheckpoint]:
        """
        Extract page state, compress DOM, generate deterministic hash, and store
        checkpoint if semantic changes are detected.
        """
        if not settings.ENABLE_CHECKPOINTING:
            logger.debug("Checkpointing disabled in settings.")
            return None

        start_time = time.time()
        try:
            if not page or page.is_closed():
                logger.warning(f"Cannot create checkpoint for session '{session_id}': Page is closed or invalid.")
                return None

            url = getattr(page, "url", "about:blank")
            page_title = await page.title() if hasattr(page, "title") else ""

            # Extract metrics asynchronously from page
            scroll_x = 0
            scroll_y = 0
            viewport_width = 1280
            viewport_height = 720
            focused_element = None

            try:
                scroll_info = await page.evaluate(
                    "() => ({ x: window.scrollX || 0, y: window.scrollY || 0, w: window.innerWidth, h: window.innerHeight })"
                )
                scroll_x = int(scroll_info.get("x", 0))
                scroll_y = int(scroll_info.get("y", 0))
                viewport_width = int(scroll_info.get("w", 1280))
                viewport_height = int(scroll_info.get("h", 720))
            except Exception:
                pass

            try:
                focused_element = await page.evaluate(
                    "() => document.activeElement ? (document.activeElement.id ? '#' + document.activeElement.id : document.activeElement.tagName.toLowerCase()) : null"
                )
            except Exception:
                pass

            # Reuse existing extraction & compression pipeline
            extracted = await extractor.extract(page)
            compressed_dom = compressor.compress(extracted)
            dom_hash = self.compute_dom_hash(extracted.get("html"))

            # Check if state changed since last checkpoint
            last_hash = self._last_hashes.get(session_id)
            last_url = self._last_urls.get(session_id)

            if last_hash == dom_hash and last_url == url:
                logger.info(f"Checkpoint Skipped for session '{session_id}' (No URL or DOM hash change).")
                return None

            checkpoint_meta = metadata or {}
            checkpoint_meta["action_trigger"] = action_trigger
            checkpoint_meta["creation_latency_ms"] = round((time.time() - start_time) * 1000, 2)

            checkpoint = DOMCheckpoint(
                session_id=session_id,
                timestamp=time.time(),
                url=url,
                page_title=page_title,
                compressed_dom=compressed_dom,
                dom_hash=dom_hash,
                scroll_x=scroll_x,
                scroll_y=scroll_y,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
                focused_element=focused_element,
                checkpoint_version="1.0",
                metadata=checkpoint_meta
            )

            # Persist to database
            def _save():
                return dom_checkpoint_db.save_checkpoint(
                    checkpoint.model_dump(),
                    max_checkpoints=settings.MAX_CHECKPOINTS,
                    retention_days=settings.CHECKPOINT_RETENTION_DAYS
                )

            if settings.ASYNC_CHECKPOINTING:
                loop = asyncio.get_event_loop()
                checkpoint_id = await loop.run_in_executor(None, _save)
            else:
                checkpoint_id = _save()

            checkpoint.checkpoint_id = checkpoint_id
            self._last_hashes[session_id] = dom_hash
            self._last_urls[session_id] = url

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Checkpoint Created: ID={checkpoint_id}, Session='{session_id}', "
                f"URL='{url}', Hash={dom_hash[:8]}, Trigger='{action_trigger}' ({elapsed_ms:.1f}ms)"
            )
            return checkpoint

        except Exception as e:
            logger.error(f"Failed to create checkpoint for session '{session_id}': {e}")
            return None

    def detect_failure(self, exception: Exception) -> Tuple[bool, str, str]:
        """
        Categorize an exception to determine whether it is a recoverable browser/network failure.

        Returns:
            Tuple[is_recoverable, failure_category, description]
        """
        err_msg = str(exception).lower()

        if "target page, context or browser has been closed" in err_msg or "target closed" in err_msg:
            return True, "BROWSER_CLOSED", "Browser or page target was unexpectedly closed."
        elif "browser has been closed" in err_msg or "browser closed" in err_msg:
            return True, "BROWSER_CRASH", "Browser process terminated or crashed."
        elif "websocket" in err_msg or "connection closed" in err_msg or "ws" in err_msg:
            return True, "WEBSOCKET_DISCONNECT", "Playwright WebSocket connection was disconnected."
        elif "timeout" in err_msg or "timed out" in err_msg:
            return True, "NAVIGATION_TIMEOUT", "Navigation or action timed out."
        elif "net::err" in err_msg or "network" in err_msg or "dns" in err_msg:
            return True, "NETWORK_INTERRUPTION", "Network error or connection loss."
        elif isinstance(exception, PlaywrightError):
            return True, "PLAYWRIGHT_ERROR", f"Playwright driver error: {str(exception)}"

        return False, "UNCLASSIFIED_ERROR", str(exception)

    def calculate_recovery_confidence(
        self,
        stored: DOMCheckpoint,
        live_url: str,
        live_title: str,
        live_dom_hash: str,
        live_ui: List[Dict[str, Any]]
    ) -> RecoveryConfidenceResult:
        """
        Validate recovered live page state against stored checkpoint and score confidence (0.0 to 1.0).

        Scoring weights:
        - URL match: 40 points
        - DOM Hash / Similarity match: 35 points
        - Page Title match: 15 points
        - Critical UI elements presence: 10 points
        """
        url_score = 0.0
        dom_score = 0.0
        title_score = 0.0
        elements_score = 0.0

        differences = {}

        # 1. URL Match (40 pts)
        if live_url == stored.url:
            url_score = 40.0
        elif live_url.rstrip("/").split("?")[0] == stored.url.rstrip("/").split("?")[0]:
            url_score = 25.0
            differences["url"] = {"stored": stored.url, "live": live_url, "note": "Query parameters mismatch"}
        else:
            url_score = 0.0
            differences["url"] = {"stored": stored.url, "live": live_url, "note": "URL mismatch"}

        # 2. DOM Hash / Similarity (35 pts)
        if live_dom_hash and live_dom_hash == stored.dom_hash:
            dom_score = 35.0
        else:
            stored_ui = stored.compressed_dom.get("ui", []) if stored.compressed_dom else []
            if stored_ui and live_ui:
                stored_tags = [f"{el.get('tag')}:{el.get('id') or el.get('name') or el.get('text', '')[:10]}" for el in stored_ui]
                live_tags = [f"{el.get('tag')}:{el.get('id') or el.get('name') or el.get('text', '')[:10]}" for el in live_ui]

                common = set(stored_tags).intersection(set(live_tags))
                ratio = len(common) / max(len(stored_tags), len(live_tags), 1)
                dom_score = round(ratio * 35.0, 2)
                differences["dom"] = {"stored_elements": len(stored_ui), "live_elements": len(live_ui), "overlap_pct": round(ratio * 100, 1)}
            else:
                dom_score = 0.0
                differences["dom"] = {"note": "DOM hash mismatch and no UI elements available for comparison"}

        # 3. Title Match (15 pts)
        if live_title == stored.page_title:
            title_score = 15.0
        elif stored.page_title and live_title and (stored.page_title in live_title or live_title in stored.page_title):
            title_score = 8.0
            differences["title"] = {"stored": stored.page_title, "live": live_title, "note": "Partial title match"}
        else:
            title_score = 0.0
            differences["title"] = {"stored": stored.page_title, "live": live_title, "note": "Title mismatch"}

        # 4. Critical Elements Match (10 pts)
        stored_ui = stored.compressed_dom.get("ui", []) if stored.compressed_dom else []
        stored_interactive = sum(1 for el in stored_ui if el.get("tag") in ("button", "input", "select", "form"))
        live_interactive = sum(1 for el in live_ui if el.get("tag") in ("button", "input", "select", "form"))

        if stored_interactive == 0 and live_interactive == 0:
            elements_score = 10.0
        elif stored_interactive > 0 and live_interactive > 0:
            ratio = min(stored_interactive, live_interactive) / max(stored_interactive, live_interactive)
            elements_score = round(ratio * 10.0, 2)
        else:
            elements_score = 0.0

        total_score = round((url_score + dom_score + title_score + elements_score) / 100.0, 2)

        if total_score >= 0.95:
            status = "EXACT_MATCH"
            reason = "Recovered page state matches stored checkpoint exactly."
        elif total_score >= settings.MINIMUM_RESUME_CONFIDENCE:
            status = "HIGH_CONFIDENCE"
            reason = f"Recovered page state is structurally valid (Score: {total_score:.2f}). Safe to auto-resume."
        elif total_score >= 0.40:
            status = "PARTIAL_MATCH"
            reason = f"Recovered page state differs partially from checkpoint (Score: {total_score:.2f})."
        else:
            status = "MISMATCH"
            reason = f"Recovered page state significantly deviates from checkpoint (Score: {total_score:.2f})."

        can_auto_resume = total_score >= settings.MINIMUM_RESUME_CONFIDENCE

        return RecoveryConfidenceResult(
            confidence=total_score,
            status=status,
            reason=reason,
            can_auto_resume=can_auto_resume,
            differences=differences,
            breakdown={
                "url_score": url_score,
                "dom_score": dom_score,
                "title_score": title_score,
                "elements_score": elements_score
            }
        )

    def load_latest_checkpoint(self, session_id: str = "default") -> Optional[DOMCheckpoint]:
        """
        Load the most recent checkpoint for a given session ID.
        """
        raw = dom_checkpoint_db.get_latest_checkpoint(session_id)
        if raw:
            return DOMCheckpoint.model_validate(raw)
        return None

    async def restore_checkpoint(
        self,
        session_id: str = "default",
        browser_manager: Any = None
    ) -> Dict[str, Any]:
        """
        Execute checkpoint restoration flow:
        1. Pause command execution for session.
        2. Load latest checkpoint.
        3. Re-initialize browser context / Playwright page.
        4. Re-navigate to checkpoint URL.
        5. Restore scroll offset and focused element.
        6. Extract fresh page state and compute confidence score.
        7. Auto-resume if confidence >= MINIMUM_RESUME_CONFIDENCE or return structured diagnostic report.
        """
        async with self._get_session_lock(session_id):
            start_time = time.time()
            logger.info(f"Recovery Started for session '{session_id}'...")

            checkpoint = self.load_latest_checkpoint(session_id)
            if not checkpoint:
                logger.error(f"Recovery Failed for session '{session_id}': No checkpoint found.")
                return {
                    "success": False,
                    "recovered": False,
                    "reason": f"No checkpoint exists for session '{session_id}'.",
                    "session_id": session_id
                }

            if browser_manager is None:
                from browser_optimizer.browser.manager import manager as default_browser_manager
                browser_manager = default_browser_manager

            try:
                # Close broken page/context if present and get fresh page
                page = await browser_manager.get_page(session_id)

                # Re-navigate to checkpoint URL
                logger.info(f"Re-navigating to checkpoint URL '{checkpoint.url}' for session '{session_id}'...")
                await page.goto(checkpoint.url, timeout=settings.BROWSER_TIMEOUT, wait_until="domcontentloaded")

                # Restore scroll position if non-zero
                if checkpoint.scroll_x > 0 or checkpoint.scroll_y > 0:
                    try:
                        await page.evaluate(f"window.scrollTo({checkpoint.scroll_x}, {checkpoint.scroll_y})")
                    except Exception as e:
                        logger.debug(f"Scroll restoration omitted: {e}")

                # Restore focused element if available
                if checkpoint.focused_element:
                    try:
                        await page.focus(checkpoint.focused_element, timeout=2000)
                    except Exception:
                        pass

                # Extract fresh live state to compute validation confidence score
                live_extracted = await extractor.extract(page)
                live_compressed = compressor.compress(live_extracted)
                live_url = getattr(page, "url", checkpoint.url)
                live_title = await page.title() if hasattr(page, "title") else ""
                live_hash = self.compute_dom_hash(live_extracted.get("html"))
                live_ui = live_compressed.get("ui", [])

                confidence_result = self.calculate_recovery_confidence(
                    checkpoint, live_url, live_title, live_hash, live_ui
                )

                elapsed_ms = (time.time() - start_time) * 1000

                if confidence_result.can_auto_resume:
                    logger.info(
                        f"Recovery Successful for session '{session_id}': "
                        f"Confidence={confidence_result.confidence:.2f} ({confidence_result.status}) in {elapsed_ms:.1f}ms"
                    )
                    # Re-save session state
                    await browser_manager.save_session_state(session_id)

                    return {
                        "success": True,
                        "recovered": True,
                        "auto_resumed": True,
                        "confidence": confidence_result.confidence,
                        "status": confidence_result.status,
                        "reason": confidence_result.reason,
                        "checkpoint_id": checkpoint.checkpoint_id,
                        "url": live_url,
                        "title": live_title,
                        "elapsed_ms": round(elapsed_ms, 2)
                    }
                else:
                    logger.warning(
                        f"Recovery Validation Failed for session '{session_id}': "
                        f"Confidence={confidence_result.confidence:.2f} < threshold ({settings.MINIMUM_RESUME_CONFIDENCE})"
                    )
                    return {
                        "success": False,
                        "recovered": True,
                        "auto_resumed": False,
                        "confidence": confidence_result.confidence,
                        "status": confidence_result.status,
                        "reason": confidence_result.reason,
                        "differences": confidence_result.differences,
                        "checkpoint_id": checkpoint.checkpoint_id,
                        "url": live_url,
                        "recommended_next_step": "Inspect differences and execute context extraction or navigation manually.",
                        "elapsed_ms": round(elapsed_ms, 2)
                    }

            except Exception as e:
                logger.error(f"Recovery Execution Failed for session '{session_id}': {e}")
                return {
                    "success": False,
                    "recovered": False,
                    "reason": f"Failed to restore page state: {str(e)}",
                    "session_id": session_id
                }

    def compare_checkpoint(
        self,
        checkpoint_a: DOMCheckpoint,
        checkpoint_b_or_live: Any
    ) -> Dict[str, Any]:
        """
        Compare two checkpoints or a checkpoint against a live page state.
        Returns added, removed, and changed UI elements.
        """
        ui_a = checkpoint_a.compressed_dom.get("ui", []) if checkpoint_a.compressed_dom else []

        if isinstance(checkpoint_b_or_live, DOMCheckpoint):
            ui_b = checkpoint_b_or_live.compressed_dom.get("ui", []) if checkpoint_b_or_live.compressed_dom else []
            url_b = checkpoint_b_or_live.url
        elif isinstance(checkpoint_b_or_live, dict):
            ui_b = checkpoint_b_or_live.get("ui", [])
            url_b = checkpoint_b_or_live.get("url", checkpoint_a.url)
        else:
            ui_b = []
            url_b = checkpoint_a.url

        from browser_optimizer.diff.diff import difference_engine
        diff = difference_engine.compute_diff(url_b, ui_b)
        return {
            "url_a": checkpoint_a.url,
            "url_b": url_b,
            "diff": diff
        }

    def delete_session_checkpoints(self, session_id: str = "default"):
        """
        Purge all stored checkpoints for a specific session ID.
        """
        dom_checkpoint_db.delete_session_checkpoints(session_id)
        self._last_hashes.pop(session_id, None)
        self._last_urls.pop(session_id, None)
        logger.info(f"Checkpoint Deleted: All checkpoints purged for session '{session_id}'.")


# Shared instance export
recovery_manager = RecoveryManager()
