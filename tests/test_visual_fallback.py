"""
Tests for Section 1.2: Visual Fallback for unreadable / canvas-heavy pages.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from browser_optimizer.extractor.vision import VisionAnalyzer, vision_analyzer
from browser_optimizer.extractor.extractor import PageExtractor
from browser_optimizer.compressor.compressor import ContextCompressor, compressor
from browser_optimizer.config.settings import settings


@pytest.mark.anyio
async def test_heuristic_visual_fallback():
    """Test that VisionAnalyzer returns fallback visual elements when Groq API key is missing/unreachable."""
    mock_page = MagicMock()
    mock_page.url = "http://example.com/canvas-game"
    
    analyzer = VisionAnalyzer()
    elements = await analyzer._heuristic_visual_fallback(mock_page)
    
    assert len(elements) >= 2
    assert any(el["visual_fallback"] is True for el in elements)
    assert any("visual" in el["id"] for el in elements)


@pytest.mark.anyio
async def test_vision_analyzer_groq_json_parsing():
    """Test parsing of Groq Vision API JSON response."""
    analyzer = VisionAnalyzer()
    
    json_response_content = (
        '```json\n'
        '[\n'
        '  {"tag": "button", "text": "Play Game", "id": "btn_play", "type": "button"},\n'
        '  {"tag": "input", "text": "Score Input", "id": "score_input", "type": "text"}\n'
        ']\n'
        '```'
    )
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json_response_content
                }
            }
        ]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        elements = await analyzer._call_groq_vision_api("data:image/jpeg;base64,dummy", "mock_key")
        
        assert len(elements) == 2
        assert elements[0]["tag"] == "button"
        assert elements[0]["text"] == "Play Game"
        assert elements[0]["visual_fallback"] is True
        assert elements[1]["tag"] == "input"


@pytest.mark.anyio
async def test_extractor_triggers_visual_fallback_below_threshold():
    """Test that PageExtractor triggers visual fallback when interactive element count < VISUAL_FALLBACK_THRESHOLD."""
    mock_page = AsyncMock()
    # HTML with 0 interactive elements (canvas heavy)
    mock_page.content.return_value = "<html><body><canvas id='webgl'></canvas></body></html>"
    mock_page.url = "http://example.com/canvas"
    mock_page.title.return_value = "Canvas WebGL App"

    # Mock aria snapshot
    mock_ax = MagicMock()
    mock_ax.aria_snapshot = AsyncMock(return_value="canvas")
    mock_page.locator.return_value = mock_ax

    mock_vision_elements = [
        {"tag": "button", "text": "Start Render", "id": "start_render", "visual_fallback": True}
    ]

    extractor_inst = PageExtractor()

    with patch.object(vision_analyzer, "capture_and_analyze", new_callable=AsyncMock) as mock_vision:
        mock_vision.return_value = mock_vision_elements
        
        result = await extractor_inst.extract(mock_page)

        assert mock_vision.called
        assert result["is_visual_fallback"] is True
        assert len(result["visual_elements"]) == 1
        assert result["visual_elements"][0]["text"] == "Start Render"


def test_compressor_incorporates_visual_elements():
    """Test that ContextCompressor merges visual elements and flags visual_fallback."""
    compressor_inst = ContextCompressor()
    from bs4 import BeautifulSoup

    extracted = {
        "html": BeautifulSoup("<html><body><canvas></canvas></body></html>", "lxml"),
        "ax_tree": "canvas",
        "raw_html_length": 50,
        "url": "http://example.com/canvas",
        "title": "Canvas Page",
        "visual_elements": [
            {"tag": "button", "text": "Canvas Button", "id": "c_btn", "visual_fallback": True}
        ],
        "is_visual_fallback": True
    }

    compressed = compressor_inst.compress(extracted)

    assert compressed["visual_fallback"] is True
    assert len(compressed["ui"]) == 1
    assert compressed["ui"][0]["text"] == "Canvas Button"
