from typing import List, Optional, Tuple
from bs4 import BeautifulSoup
from playwright.async_api import Page

from browser_optimizer.config.settings import get_settings
from browser_optimizer.extractor.vision import VisionAnalyzer
from browser_optimizer.schemas.schemas import UIElement
from browser_optimizer.utils.logger import logger


class PageExtractor:
    """
    Page Perception & Extraction Engine.
    Extracts raw HTML, ARIA accessibility snapshots, and counts interactive tags.
    Automatically triggers Multimodal Vision Fallback if interactive tag count < threshold.
    """
    INTERACTIVE_TAGS = {"button", "input", "textarea", "select", "a", "form", "label"}

    def __init__(self):
        self.settings = get_settings()
        self.vision_analyzer = VisionAnalyzer()

    async def extract_html(self, page: Page) -> str:
        """
        Retrieves raw DOM HTML string from active Playwright Page.
        """
        return await page.content()

    def parse_html(self, html: str) -> BeautifulSoup:
        """
        Parses HTML string into BeautifulSoup DOM tree.
        """
        try:
            return BeautifulSoup(html, "lxml")
        except Exception:
            return BeautifulSoup(html, "html.parser")

    async def extract_ax_tree(self, page: Page) -> Optional[str]:
        """
        Retrieves semantic ARIA accessibility snapshot tree via Playwright locator.
        """
        try:
            ax_snapshot = await page.locator("body").aria_snapshot()
            return ax_snapshot
        except Exception as e:
            logger.warning(f"Failed to extract ARIA snapshot: {e}")
            return None

    def count_interactive_elements(self, soup: BeautifulSoup) -> int:
        """
        Counts the total number of interactive tags in parsed DOM.
        """
        count = 0
        for tag in soup.find_all(self.INTERACTIVE_TAGS):
            count += 1
        return count

    async def extract_page_data(self, page: Page) -> Tuple[str, BeautifulSoup, Optional[str], List[UIElement]]:
        """
        Main extraction entry point.
        Retrieves raw HTML, ARIA snapshot, parses DOM, checks interactive tag threshold,
        and invokes Multimodal Vision Analyzer if interactive tags < VISUAL_FALLBACK_THRESHOLD.
        """
        raw_html = await self.extract_html(page)
        soup = self.parse_html(raw_html)
        ax_tree = await self.extract_ax_tree(page)

        interactive_count = self.count_interactive_elements(soup)
        logger.info(f"Page extracted. Interactive DOM tags count: {interactive_count}")

        visual_elements: List[UIElement] = []
        if interactive_count < self.settings.VISUAL_FALLBACK_THRESHOLD:
            logger.warning(
                f"Interactive DOM tag count ({interactive_count}) below threshold "
                f"({self.settings.VISUAL_FALLBACK_THRESHOLD}). Triggering Vision Analyzer."
            )
            visual_elements = await self.vision_analyzer.capture_and_analyze(page)

        return raw_html, soup, ax_tree, visual_elements
