from bs4 import BeautifulSoup
from browser_optimizer.compressor.compressor import ContextCompressor
from browser_optimizer.schemas.schemas import UIElement


def test_clean_dom_prunes_noise_tags():
    compressor = ContextCompressor()
    html_with_noise = """
    <html>
        <head>
            <style>body { color: red; }</style>
            <script>console.log("script");</script>
        </head>
        <body>
            <header>Header content</header>
            <div>Main Content</div>
            <svg><path d="M0 0h10v10H0z"/></svg>
            <footer>Footer content</footer>
        </body>
    </html>
    """
    soup = BeautifulSoup(html_with_noise, "html.parser")
    compressor.clean_dom(soup)
    
    assert soup.find("script") is None
    assert soup.find("style") is None
    assert soup.find("header") is None
    assert soup.find("footer") is None
    assert soup.find("svg") is None
    assert "Main Content" in soup.get_text()


def test_compressor_ui_extraction():
    compressor = ContextCompressor()
    sample_html = """
    <html>
        <body>
            <button id="submit-btn" type="submit">Submit Order</button>
            <input type="text" name="email" placeholder="user@example.com" />
            <a href="/help">Help Center</a>
        </body>
    </html>
    """
    soup = BeautifulSoup(sample_html, "html.parser")
    ui_elements = compressor.extract_ui(soup)
    
    assert len(ui_elements) == 3
    tags = [e.tag for e in ui_elements]
    assert "button" in tags
    assert "input" in tags
    assert "a" in tags
    
    btn = next(e for e in ui_elements if e.tag == "button")
    assert btn.text == "Submit Order"
    assert btn.id == "submit-btn"
    assert btn.selector == "#submit-btn"


def test_compressor_context_creation():
    compressor = ContextCompressor()
    raw_html = "<html><body><h1>Hello World</h1><button id='b'>Click</button></body></html>"
    soup = BeautifulSoup(raw_html, "html.parser")
    
    context = compressor.compress(
        raw_html=raw_html,
        soup=soup,
        url="https://example.com",
        title="Test Page"
    )
    
    assert context.url == "https://example.com"
    assert context.title == "Test Page"
    assert context.raw_html_length == len(raw_html.encode("utf-8"))
    assert context.compressed_length > 0
    assert len(context.ui) == 1
    assert context.ui[0].id == "b"
