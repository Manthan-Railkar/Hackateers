import asyncio
import time
import pytest
from browser_optimizer.config.settings import settings
from browser_optimizer.schemas.schemas import LLMSDiscoveryResult, NavigationStrategyResult
from browser_optimizer.cache.db import llms_cache_db
from browser_optimizer.discovery.parser import llms_parser
from browser_optimizer.discovery.manager import llms_discovery_manager
from browser_optimizer.metrics.metrics import metrics


@pytest.fixture
def clean_llms_cache():
    llms_cache_db.invalidate_cache("testdocs.org")
    llms_cache_db.invalidate_cache("example.com")
    yield
    llms_cache_db.invalidate_cache("testdocs.org")
    llms_cache_db.invalidate_cache("example.com")


def test_parse_valid_llms_markdown():
    """Verify parsing a valid llms.txt Markdown with headings, links, comments, and metadata."""
    markdown = """# Project Documentation v2.1.0
<!-- Internal build comment -->
> Version: 2.1.0
> Repository: https://github.com/example/project

## Documentation
- [Getting Started](/docs/quickstart): Fast track guide
- [Architecture Guide](https://testdocs.org/docs/arch): System design

## API Reference
- [REST API](/api/v1/reference): Complete HTTP endpoints
- [OpenAPI Spec](/api/openapi.json): OpenAPI 3.0 file

## Guides
- [CLI Reference](/guides/cli): Command line tool

## Examples
- [Python Demo](/examples/python-demo): Python usage example
"""

    result = llms_parser.parse(markdown, base_url="https://testdocs.org")

    assert result.supported is True
    assert result.version == "2.1.0" or result.version == "2.1"
    assert result.repository == "https://github.com/example/project"
    assert len(result.documentation) == 2
    assert result.documentation[0].title == "Getting Started"
    assert result.documentation[0].url == "https://testdocs.org/docs/quickstart"
    assert result.documentation[1].url == "https://testdocs.org/docs/arch"

    assert len(result.api_reference) == 2
    assert result.api_reference[0].url == "https://testdocs.org/api/v1/reference"
    assert len(result.guides) == 1
    assert len(result.examples) == 1
    assert len(result.discovered_urls) == 6


def test_parse_malformed_llms_markdown():
    """Verify parser handles empty strings, malformed markdown, and unknown sections safely."""
    res_empty = llms_parser.parse("")
    assert res_empty.supported is False

    malformed = """
    Random text without headings
    - Just a list item with no link
    - [Broken Link](
    ### Unknown Custom Section
    - [Valid Link](/valid): Some description
    """

    res_malformed = llms_parser.parse(malformed, base_url="https://example.com")
    assert res_malformed.supported is True
    assert len(res_malformed.documentation) == 1
    assert res_malformed.documentation[0].url == "https://example.com/valid"


def test_llms_cache_persistence_and_expiry(clean_llms_cache):
    """Verify saving to SQLite llms_cache table, retrieving, and TTL expiry."""
    hostname = "testdocs.org"
    parsed_data = {"supported": True, "version": "1.0", "discovered_urls": ["https://testdocs.org/docs"]}

    llms_cache_db.save_llms_cache(
        hostname,
        raw_content="# Test",
        parsed_dict=parsed_data,
        etag='"etag-123"',
        last_modified="Mon, 01 Jan 2026 00:00:00 GMT",
        ttl=3600
    )

    cached = llms_cache_db.get_llms_cache(hostname)
    assert cached is not None
    assert cached["etag"] == '"etag-123"'
    assert cached["is_expired"] is False
    assert cached["parsed"]["version"] == "1.0"

    # Test expired lookup
    llms_cache_db.save_llms_cache(
        hostname,
        raw_content="# Test",
        parsed_dict=parsed_data,
        ttl=-10  # Expired
    )
    cached_expired = llms_cache_db.get_llms_cache(hostname)
    assert cached_expired["is_expired"] is True


@pytest.mark.asyncio
async def test_decision_engine_strategy_selection(clean_llms_cache):
    """Verify decision engine selects DIRECT_FETCH for docs vs PLAYWRIGHT for auth/app pages."""
    # Pre-seed cache with supported llms.txt
    llms_cache_db.save_llms_cache(
        "testdocs.org",
        raw_content="# Docs",
        parsed_dict={
            "supported": True,
            "discovered_urls": ["https://testdocs.org/docs/overview", "https://testdocs.org/api/reference"]
        },
        ttl=3600
    )

    # 1. Listed documentation URL -> DIRECT_FETCH
    strat_docs = await llms_discovery_manager.select_navigation_strategy("https://testdocs.org/docs/overview")
    assert strat_docs.strategy == "DIRECT_FETCH"
    assert strat_docs.confidence >= 0.85

    # 2. Raw markdown / spec file -> DIRECT_FETCH
    strat_raw = await llms_discovery_manager.select_navigation_strategy("https://example.com/openapi.json")
    assert strat_raw.strategy == "DIRECT_FETCH"

    # 3. Login / Auth / Application URL -> PLAYWRIGHT
    strat_login = await llms_discovery_manager.select_navigation_strategy("https://testdocs.org/login")
    assert strat_login.strategy == "PLAYWRIGHT"

    strat_checkout = await llms_discovery_manager.select_navigation_strategy("https://example.com/checkout/payment")
    assert strat_checkout.strategy == "PLAYWRIGHT"


@pytest.mark.asyncio
async def test_direct_fetch_pipeline(monkeypatch):
    """Test Direct Fetch pipeline downloading HTML and extracting UI without Playwright."""
    sample_html = """
    <html>
        <head><title>Direct Docs</title></head>
        <body>
            <h1>Documentation Overview</h1>
            <p>Welcome to the API reference.</p>
            <a href="/docs/next">Next Page</a>
            <button id="copy-btn">Copy Code</button>
        </body>
    </html>
    """

    class MockResponse:
        status_code = 200
        text = sample_html
        def raise_for_status(self): pass

    class MockClient:
        is_closed = False
        async def get(self, url, headers=None):
            return MockResponse()

    async def mock_get_client():
        return MockClient()

    monkeypatch.setattr(llms_discovery_manager, "_get_client", mock_get_client)

    result = await llms_discovery_manager.direct_fetch("https://testdocs.org/docs/overview")

    assert result["title"] == "Direct Docs"
    assert result["from_direct_fetch"] is True
    assert result["browser_avoided"] is True
    assert len(result["ui"]) >= 2

    # Check metrics recorded
    stats = metrics.get_stats()
    assert stats["llms_discovery"]["direct_fetch_count"] > 0
