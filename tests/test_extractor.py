import pytest
from bs4 import BeautifulSoup
from browser_optimizer.extractor.extractor import PageExtractor
from browser_optimizer.extractor.vision import VisionAnalyzer


def test_parse_html_and_count_interactive():
    extractor = PageExtractor()
    sample_html = """
    <html>
        <body>
            <h1>Title</h1>
            <p>Some paragraph text.</p>
            <button id="btn1">Click Me</button>
            <input type="text" name="username" placeholder="Enter name" />
            <a href="https://example.com">Link</a>
            <form action="/submit">
                <input type="submit" value="Submit" />
            </form>
        </body>
    </html>
    """
    soup = extractor.parse_html(sample_html)
    assert isinstance(soup, BeautifulSoup)
    
    count = extractor.count_interactive_elements(soup)
    assert count >= 4  # button, input, a, form, input[submit]


def test_vision_fallback_synthetic_generation():
    analyzer = VisionAnalyzer()
    synthetic = analyzer._generate_synthetic_visual_elements()
    assert len(synthetic) >= 3
    tags = [e.tag for e in synthetic]
    assert "canvas" in tags
    assert "button" in tags
    assert "input" in tags


@pytest.mark.asyncio
async def test_page_extractor_with_live_page(tmp_path):
    from browser_optimizer.browser.manager import BrowserManager
    manager = BrowserManager()
    try:
        page = await manager.navigate("https://example.com", session_id="extractor_test")
        extractor = PageExtractor()
        raw_html, soup, ax_tree, visual_elements = await extractor.extract_page_data(page)
        
        assert raw_html is not None
        assert len(raw_html) > 0
        assert soup is not None
    finally:
        await manager.stop()
