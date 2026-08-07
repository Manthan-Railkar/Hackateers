"""
LLMS.txt Markdown Parser.
Parses markdown files conforming to the llms.txt standard into structured discovery results.
Categorizes sections, resolves relative and absolute URLs, strips HTML comments, and extracts metadata.
"""

import re
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse

from browser_optimizer.schemas.schemas import LLMSDiscoveryResult, LLMSSectionItem
from browser_optimizer.utils.logger import logger


class LLMSParser:
    """
    Parser for llms.txt standard files.
    Transforms raw Markdown into structured LLMSDiscoveryResult schema.
    """

    SECTION_MAPPING = {
        "documentation": "documentation",
        "docs": "documentation",
        "doc": "documentation",
        "api": "api_reference",
        "api reference": "api_reference",
        "api-reference": "api_reference",
        "apis": "api_reference",
        "guides": "guides",
        "guide": "guides",
        "tutorials": "tutorials",
        "tutorial": "tutorials",
        "examples": "examples",
        "example": "examples",
        "samples": "examples",
        "openapi": "openapi",
        "swagger": "openapi",
        "changelog": "changelog",
        "release notes": "changelog",
        "changes": "changelog",
        "quick start": "guides",
        "quickstart": "guides",
        "sdk": "api_reference",
        "sdks": "api_reference",
        "cli": "guides",
        "resources": "documentation",
    }

    def parse(self, markdown_text: str, base_url: str = "") -> LLMSDiscoveryResult:
        """
        Parse raw llms.txt Markdown text into a structured LLMSDiscoveryResult.
        
        Args:
            markdown_text (str): Raw Markdown string.
            base_url (str): Target base URL for resolving relative links.
            
        Returns:
            LLMSDiscoveryResult: Structured Pydantic model with categorized sections and links.
        """
        if not markdown_text or not isinstance(markdown_text, str):
            return LLMSDiscoveryResult(supported=False, raw_markdown="")

        # Strip HTML comments
        clean_markdown = re.sub(r"<!--.*?-->", "", markdown_text, flags=re.DOTALL)

        lines = clean_markdown.splitlines()

        documentation: List[LLMSSectionItem] = []
        api_reference: List[LLMSSectionItem] = []
        guides: List[LLMSSectionItem] = []
        tutorials: List[LLMSSectionItem] = []
        examples: List[LLMSSectionItem] = []
        openapi: List[LLMSSectionItem] = []
        changelog: List[LLMSSectionItem] = []

        repository: Optional[str] = None
        sitemap: Optional[str] = None
        version: Optional[str] = None
        all_urls: List[str] = []

        current_section = "documentation"  # Default section

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # Check heading lines
            if line_str.startswith("#"):
                heading_text = line_str.lstrip("#").strip().lower()

                # Extract version if present in title/heading
                ver_match = re.search(r"v?(\d+\.\d+(\.\d+)?)", heading_text)
                if ver_match and not version:
                    version = ver_match.group(1)

                # Match heading to mapped section
                matched_sec = None
                for key, mapped in self.SECTION_MAPPING.items():
                    if key in heading_text:
                        matched_sec = mapped
                        break

                if matched_sec:
                    current_section = matched_sec
                continue

            # Check blockquote / metadata lines (e.g. > Repository: https://github.com/...)
            if line_str.startswith(">"):
                meta_text = line_str.lstrip(">").strip()
                if "repository" in meta_text.lower() or "github" in meta_text.lower():
                    repo_url_match = re.search(r"https?://[^\s]+", meta_text)
                    if repo_url_match:
                        repository = repo_url_match.group(0).rstrip(").,")
                if "version" in meta_text.lower() and not version:
                    ver_match = re.search(r"v?(\d+\.\d+(\.\d+)?)", meta_text)
                    if ver_match:
                        version = ver_match.group(1)
                continue

            # Check list items (- [Title](url): description OR * [Title](url))
            list_match = re.match(r"^[\-\*\+\d\.]+\s+(.*)$", line_str)
            if list_match:
                item_text = list_match.group(1).strip()
                link_match = re.search(r"\[([^\]]+)\]\(([^)]+)\)(?::?\s*(.*))?", item_text)

                if link_match:
                    title = link_match.group(1).strip()
                    raw_url = link_match.group(2).strip()
                    desc = link_match.group(3).strip() if link_match.group(3) else None

                    # Resolve relative URLs against base_url
                    resolved_url = urljoin(base_url, raw_url) if base_url else raw_url
                    all_urls.append(resolved_url)

                    # Check special URLs (repository or sitemap)
                    if "sitemap" in title.lower() or "sitemap.xml" in raw_url.lower():
                        sitemap = resolved_url
                    elif ("repository" in title.lower() or "github.com" in raw_url.lower()) and not repository:
                        repository = resolved_url

                    section_item = LLMSSectionItem(title=title, url=resolved_url, description=desc)

                    if current_section == "documentation":
                        documentation.append(section_item)
                    elif current_section == "api_reference":
                        api_reference.append(section_item)
                    elif current_section == "guides":
                        guides.append(section_item)
                    elif current_section == "tutorials":
                        tutorials.append(section_item)
                    elif current_section == "examples":
                        examples.append(section_item)
                    elif current_section == "openapi":
                        openapi.append(section_item)
                    elif current_section == "changelog":
                        changelog.append(section_item)
                    else:
                        documentation.append(section_item)

        # Deduplicate discovered URLs
        unique_urls = list(dict.fromkeys(all_urls))

        return LLMSDiscoveryResult(
            supported=True,
            version=version,
            documentation=documentation,
            api_reference=api_reference,
            guides=guides,
            tutorials=tutorials,
            examples=examples,
            openapi=openapi,
            changelog=changelog,
            repository=repository,
            sitemap=sitemap,
            raw_markdown=markdown_text,
            discovered_urls=unique_urls
        )


# Shared parser instance
llms_parser = LLMSParser()
