"""
LLMSDiscoveryManager module.
Provides intelligent website discovery via llms.txt standard, caching,
decision engine strategy selection, and Playwright-bypassing Direct Fetch pipeline.
"""

import asyncio
import re
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urlparse, urljoin
import httpx

from browser_optimizer.config.settings import settings
from browser_optimizer.utils.logger import logger
from browser_optimizer.schemas.schemas import (
    LLMSDiscoveryResult,
    NavigationStrategyResult,
    LLMSSectionItem
)
from browser_optimizer.cache.db import llms_cache_db
from browser_optimizer.discovery.parser import llms_parser
from browser_optimizer.extractor.extractor import extractor
from browser_optimizer.compressor.compressor import compressor
from browser_optimizer.classifier.classifier import classifier as page_classifier
from browser_optimizer.cache.cache import semantic_cache
from browser_optimizer.metrics.metrics import metrics


class LLMSDiscoveryManager:
    """
    Subsystem managing llms.txt discovery, HTTP conditional revalidation,
    intelligent navigation strategy decision engine, and direct fetch execution.
    """

    PLAYWRIGHT_KEYWORDS = {
        "login", "signin", "auth", "signup", "register", "dashboard", "checkout",
        "cart", "search", "admin", "settings", "upload", "payment", "account",
        "workspace", "portal", "console", "app"
    }

    DIRECT_FETCH_KEYWORDS = {
        "docs", "doc", "api", "guide", "guides", "tutorial", "tutorials",
        "reference", "changelog", "openapi", "swagger", "readme", "about",
        "faq", "architecture", "overview", "manual"
    }

    def __init__(self):
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)
        return self._http_client

    def _extract_hostname(self, url_or_host: str) -> str:
        if not url_or_host:
            return ""
        if not url_or_host.startswith("http://") and not url_or_host.startswith("https://"):
            url_or_host = f"https://{url_or_host}"
        parsed = urlparse(url_or_host)
        return parsed.hostname.lower() if parsed.hostname else ""

    async def discover_llms(self, url_or_host: str, force_refresh: bool = False) -> LLMSDiscoveryResult:
        """
        Discover and parse llms.txt for a given URL or hostname.
        Checks SQLite llms_cache_db first, supports HTTP conditional revalidation (ETag/Last-Modified),
        and falls back to root /llms.txt or /www.domain.com/llms.txt.
        """
        if not settings.ENABLE_LLMS_DISCOVERY:
            return LLMSDiscoveryResult(supported=False)

        hostname = self._extract_hostname(url_or_host)
        if not hostname:
            return LLMSDiscoveryResult(supported=False)

        # Check cache if not forcing refresh
        if not force_refresh:
            cached = llms_cache_db.get_llms_cache(hostname)
            if cached and not cached.get("is_expired"):
                logger.info(f"LLMS Cache HIT for host '{hostname}'")
                parsed_data = cached.get("parsed") or {}
                return LLMSDiscoveryResult.model_validate(parsed_data)

        # Build candidate URLs
        candidate_urls = [
            f"https://{hostname}/llms.txt",
            f"https://www.{hostname}/llms.txt" if not hostname.startswith("www.") else f"https://{hostname[4:]}/llms.txt"
        ]

        cached_entry = llms_cache_db.get_llms_cache(hostname)
        etag = cached_entry.get("etag") if cached_entry else None
        last_modified = cached_entry.get("last_modified") if cached_entry else None

        client = await self._get_client()

        for target_url in candidate_urls:
            try:
                headers = {}
                if etag:
                    headers["If-None-Match"] = etag
                if last_modified:
                    headers["If-Modified-Since"] = last_modified

                response = await client.get(target_url, headers=headers)

                # HTTP 304 Not Modified -> Reuse cached content and update expiry
                if response.status_code == 304 and cached_entry:
                    logger.info(f"LLMS 304 Not Modified for '{target_url}'. Extending TTL.")
                    parsed_data = cached_entry.get("parsed") or {}
                    llms_cache_db.save_llms_cache(
                        hostname,
                        cached_entry.get("raw_content", ""),
                        parsed_data,
                        etag=etag,
                        last_modified=last_modified,
                        ttl=settings.LLMS_CACHE_TTL
                    )
                    metrics.record_llms_discovery(success=True)
                    return LLMSDiscoveryResult.model_validate(parsed_data)

                if response.status_code == 200:
                    text_content = response.text
                    if len(text_content.encode("utf-8")) <= settings.MAX_LLMS_SIZE:
                        # Parse Markdown
                        base_url = f"https://{hostname}"
                        parsed_result = llms_parser.parse(text_content, base_url=base_url)

                        new_etag = response.headers.get("etag")
                        new_last_modified = response.headers.get("last-modified")

                        llms_cache_db.save_llms_cache(
                            hostname,
                            text_content,
                            parsed_result.model_dump(),
                            etag=new_etag,
                            last_modified=new_last_modified,
                            version=parsed_result.version,
                            ttl=settings.LLMS_CACHE_TTL
                        )
                        logger.info(f"LLMS Discovered & Cached for '{hostname}': {len(parsed_result.discovered_urls)} URLs found.")
                        metrics.record_llms_discovery(success=True)
                        return parsed_result

            except Exception as e:
                logger.debug(f"Failed llms.txt discovery request for '{target_url}': {e}")

        # Discovery failed for host
        logger.info(f"LLMS Discovery MISS for host '{hostname}' (No valid llms.txt).")
        metrics.record_llms_discovery(success=False)
        return LLMSDiscoveryResult(supported=False)

    def parse_llms(self, markdown_text: str, base_url: str = "") -> LLMSDiscoveryResult:
        """
        Parse raw Markdown into structured LLMSDiscoveryResult.
        """
        return llms_parser.parse(markdown_text, base_url=base_url)

    def get_cached_llms(self, hostname: str) -> Optional[dict]:
        """
        Retrieve stored discovery record for a hostname.
        """
        clean_host = self._extract_hostname(hostname)
        return llms_cache_db.get_llms_cache(clean_host)

    async def select_navigation_strategy(self, url: str) -> NavigationStrategyResult:
        """
        Intelligent Decision Engine.
        Determines whether a URL requires PLAYWRIGHT, can be served via DIRECT_FETCH,
        or should run in HYBRID mode.
        """
        if not settings.ENABLE_LLMS_DISCOVERY or not settings.ENABLE_DIRECT_FETCH:
            return NavigationStrategyResult(
                strategy="PLAYWRIGHT",
                reason="LLMS Discovery or Direct Fetch disabled in settings.",
                confidence=1.0
            )

        parsed = urlparse(url)
        hostname = parsed.hostname.lower() if parsed.hostname else ""
        path = parsed.path.lower()

        # 1. Check Playwright-required keywords
        path_segments = set(re.split(r"[/._\-]", path))
        if path_segments.intersection(self.PLAYWRIGHT_KEYWORDS):
            metrics.record_browser_fallback()
            return NavigationStrategyResult(
                strategy="PLAYWRIGHT",
                reason=f"URL contains interactive/application keyword ({path_segments.intersection(self.PLAYWRIGHT_KEYWORDS)}).",
                confidence=0.90
            )

        # 2. Check direct file extension (e.g. .md, .txt, .json, .yaml, .xml)
        if path.endswith((".md", ".txt", ".json", ".yaml", ".yml", ".xml")):
            return NavigationStrategyResult(
                strategy="DIRECT_FETCH",
                reason="Target URL is a raw static document / spec file.",
                confidence=0.98
            )

        # 3. Check llms.txt discovery for host
        discovery = await self.discover_llms(hostname)
        if discovery.supported:
            # Check if URL is explicitly listed in discovered documentation/api URLs
            if url in discovery.discovered_urls or any(url.startswith(u) for u in discovery.discovered_urls):
                return NavigationStrategyResult(
                    strategy="DIRECT_FETCH",
                    reason=f"Host '{hostname}' supports llms.txt and URL is a listed documentation resource.",
                    confidence=0.95
                )

        # 4. Check documentation path patterns
        if any(kw in path for kw in self.DIRECT_FETCH_KEYWORDS):
            if settings.ALLOW_HYBRID_NAVIGATION and "interactive" in path:
                metrics.record_hybrid_execution()
                return NavigationStrategyResult(
                    strategy="HYBRID",
                    reason="Documentation page with potential interactive widgets.",
                    confidence=0.80
                )
            return NavigationStrategyResult(
                strategy="DIRECT_FETCH",
                reason="URL matches static documentation path patterns.",
                confidence=0.85
            )

        # Fallback to Playwright for dynamic / unclassified pages
        metrics.record_browser_fallback()
        return NavigationStrategyResult(
            strategy="PLAYWRIGHT",
            reason="Unclassified page type; defaulting to Playwright automation.",
            confidence=0.70
        )

    async def direct_fetch(self, url: str) -> Dict[str, Any]:
        """
        Direct Fetch Engine.
        Downloads HTML directly via HTTP without opening Playwright, passes markup through
        extractor & compressor, updates semantic cache, and returns semantic context payload.
        """
        start_time = time.time()
        logger.info(f"Direct Fetch Started for URL '{url}' (Bypassing Playwright)...")

        client = await self._get_client()
        try:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BrowserOptimizer/1.0"})
            response.raise_for_status()
            html_text = response.text
        except Exception as e:
            logger.warning(f"Direct Fetch HTTP request failed for '{url}': {e}. Falling back to Playwright...")
            metrics.record_browser_fallback()
            raise RuntimeError(f"Direct Fetch failed: {e}")

        # Parse HTML via BeautifulSoup and extract structured UI elements
        soup = extractor.parse_html(html_text)

        # Build extraction package mimicking Playwright Page extraction
        important_tags = {"button", "input", "textarea", "select", "label", "form", "a"}
        extracted = {
            "html": soup,
            "ax_tree": None,
            "raw_html_length": len(html_text),
            "url": url,
            "title": soup.title.string.strip() if soup and soup.title and soup.title.string else url,
            "visual_elements": [],
            "is_visual_fallback": False
        }

        # Compress context using existing compressor pipeline
        compressed = compressor.compress(extracted)
        classification = page_classifier.classify(compressed)

        # Store in semantic cache
        semantic_cache.store(url, html_text, compressed)

        elapsed_ms = (time.time() - start_time) * 1000
        # Estimated Playwright launch + DOM load latency is ~2500ms
        latency_saved_ms = max(0.0, 2500.0 - elapsed_ms)

        metrics.record_direct_fetch(latency_saved_ms=latency_saved_ms)
        metrics.record_llms_discovery(success=True, avoided_browser=True)
        metrics.record_compression(extracted["raw_html_length"], compressed["compressed_length"])

        logger.info(f"Direct Fetch Completed for '{url}' in {elapsed_ms:.1f}ms (Avoided Playwright launch).")

        return {
            "url": url,
            "title": compressed["title"],
            "ui": compressed["ui"],
            "ax_tree": compressed["ax_tree"],
            "classification": classification,
            "from_cache": False,
            "from_direct_fetch": True,
            "browser_avoided": True,
            "compression_ratio_pct": compressed["compression_ratio"],
            "latency_ms": round(elapsed_ms, 2)
        }

    def invalidate_llms_cache(self, hostname: str):
        """
        Purge stored discovery cache entry for a hostname.
        """
        clean_host = self._extract_hostname(hostname)
        llms_cache_db.invalidate_cache(clean_host)
        logger.info(f"LLMS Cache Invalidated for host '{clean_host}'.")


# Shared manager instance export
llms_discovery_manager = LLMSDiscoveryManager()
