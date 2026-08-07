import json
from typing import List, Optional
from bs4 import BeautifulSoup

from browser_optimizer.schemas.schemas import CompressedContext, UIElement
from browser_optimizer.utils.logger import logger


class ContextCompressor:
    """
    DOM Context Compressor Engine.
    Decomposes non-essential DOM tags (scripts, styles, SVGs, headers, footers),
    extracts interactive UI control elements, truncates body text,
    and formats an ultra-compact CompressedContext model with exact token/byte compression ratios.
    """
    DECOMPOSE_TAGS = {"script", "style", "footer", "header", "noscript", "svg", "iframe", "style", "nav", "aside"}
    INTERACTIVE_TAGS = {"button", "input", "textarea", "select", "a", "form", "label"}

    def clean_dom(self, soup: BeautifulSoup) -> None:
        """
        Decomposes non-essential tags from the BeautifulSoup DOM tree in-place.
        """
        for tag in soup.find_all(self.DECOMPOSE_TAGS):
            tag.decompose()

    def remove_empty(self, soup: BeautifulSoup) -> None:
        """
        Recursively decomposes tags that contain no text and no child elements.
        """
        for tag in list(soup.find_all(True)):
            if tag.name not in self.INTERACTIVE_TAGS and not tag.get_text(strip=True) and not tag.find_all(True):
                tag.decompose()

    def build_selector(self, tag) -> Optional[str]:
        """
        Builds a unique or deterministic CSS selector for a given BS4 element.
        """
        if tag.get("id"):
            return f"#{tag['id']}"
        if tag.get("name"):
            return f"{tag.name}[name='{tag['name']}']"
        if tag.get("type"):
            return f"{tag.name}[type='{tag['type']}']"
        return tag.name

    def extract_ui(self, soup: BeautifulSoup, visual_elements: Optional[List[UIElement]] = None) -> List[UIElement]:
        """
        Extracts clean UIElement objects for all interactive tags in the pruned DOM.
        Merges vision elements if provided.
        """
        ui_elements: List[UIElement] = []
        seen_keys = set()

        for tag in soup.find_all(self.INTERACTIVE_TAGS):
            text = (tag.get_text(strip=True) or tag.get("aria-label") or tag.get("value") or tag.get("title") or "").strip()
            element_id = tag.get("id")
            name = tag.get("name")
            placeholder = tag.get("placeholder")
            element_type = tag.get("type")
            href = tag.get("href")
            selector = self.build_selector(tag)

            # Deduplication key
            dedup_key = (tag.name, text, element_id, name, element_type, selector)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            ui_elements.append(UIElement(
                tag=tag.name,
                text=text if text else None,
                id=element_id,
                name=name,
                placeholder=placeholder,
                type=element_type,
                href=href,
                selector=selector,
                is_visible=True
            ))

        # Merge visual elements from Multimodal Vision analyzer if present
        if visual_elements:
            for ve in visual_elements:
                dedup_key = (ve.tag, ve.text, ve.id, ve.name, ve.type, ve.selector)
                if dedup_key not in seen_keys:
                    seen_keys.add(dedup_key)
                    ui_elements.append(ve)

        return ui_elements

    def compress(
        self,
        raw_html: str,
        soup: BeautifulSoup,
        url: str,
        title: Optional[str] = None,
        ax_tree: Optional[str] = None,
        visual_elements: Optional[List[UIElement]] = None
    ) -> CompressedContext:
        """
        Compresses raw HTML DOM into a compact CompressedContext model.
        Calculates exact byte/token compression ratio.
        """
        raw_html_length = len(raw_html.encode("utf-8"))

        # Prune DOM in-place
        self.clean_dom(soup)
        self.remove_empty(soup)

        # Extract UI elements
        ui_elements = self.extract_ui(soup, visual_elements)

        # Extract body text capped at 2,000 chars
        full_text = " ".join(soup.get_text(separator=" ").split())
        truncated_text = full_text[:2000] if full_text else None

        # Build CompressedContext model
        context = CompressedContext(
            ui=ui_elements,
            ax_tree=ax_tree,
            url=url,
            title=title,
            text_content=truncated_text,
            raw_html_length=raw_html_length,
            compressed_length=0,
            compression_ratio=0.0
        )

        # Calculate exact compressed payload JSON size & compression ratio
        compressed_json = context.model_dump_json(exclude_none=True)
        compressed_length = len(compressed_json.encode("utf-8"))

        compression_ratio = 0.0
        if raw_html_length > 0:
            compression_ratio = round((1 - (compressed_length / raw_html_length)) * 100, 1)

        context.compressed_length = compressed_length
        context.compression_ratio = compression_ratio

        logger.info(
            f"DOM Compressed for '{url}': Raw HTML={raw_html_length} bytes -> "
            f"Compressed={compressed_length} bytes ({compression_ratio}% token/byte savings)"
        )
        return context
