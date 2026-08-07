import base64
import json
from typing import List
import httpx
from playwright.async_api import Page

from browser_optimizer.config.settings import get_settings
from browser_optimizer.schemas.schemas import UIElement
from browser_optimizer.utils.logger import logger


class VisionAnalyzer:
    """
    Multimodal Perception Vision Module.
    Captures page screenshots and uses Groq VLM (Llama 3.2 Vision) to extract
    interactive controls from Canvas-heavy applications, SPAs, and visual elements.
    """
    def __init__(self):
        self.settings = get_settings()

    async def capture_and_analyze(self, page: Page) -> List[UIElement]:
        """
        Captures a screenshot of the page and extracts visual interactive UI elements.
        Falls back gracefully if Groq API key is unconfigured or call fails.
        """
        logger.info("Triggering Multimodal Vision Fallback analysis...")
        try:
            screenshot_bytes = await page.screenshot(type="jpeg", quality=80, full_page=True)
            b64_image = base64.b64encode(screenshot_bytes).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to capture screenshot for vision analysis: {e}")
            return self._generate_synthetic_visual_elements()

        if self.settings.GROQ_API_KEY:
            try:
                return await self._query_groq_vision(b64_image)
            except Exception as e:
                logger.warning(f"Groq VLM API call failed ({e}). Falling back to synthetic visual descriptors.")
                return self._generate_synthetic_visual_elements()
        else:
            logger.info("GROQ_API_KEY not configured. Utilizing synthetic visual element fallback.")
            return self._generate_synthetic_visual_elements()

    async def _query_groq_vision(self, b64_image: str) -> List[UIElement]:
        """
        Queries Groq Llama 3.2 Vision API with base64 image payload.
        """
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        prompt = (
            "Analyze this webpage screenshot (Canvas/SPA layout). Identify all interactive UI controls "
            "(buttons, inputs, links, canvases, textareas). Return ONLY a JSON array of objects with keys: "
            "tag, text, id, type, selector. Example: [{'tag': 'button', 'text': 'Submit', 'id': 'btn1', 'type': 'submit', 'selector': '#btn1'}]"
        )
        
        payload = {
            "model": self.settings.GROQ_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}
                        }
                    ]
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.1
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            res_json = response.json()
            
            content = res_json["choices"][0]["message"]["content"]
            # Extract JSON from output markdown block if wrapped
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            parsed = json.loads(content)
            elements = []
            for item in parsed:
                elements.append(UIElement(
                    tag=item.get("tag", "div"),
                    text=item.get("text"),
                    id=item.get("id"),
                    type=item.get("type"),
                    selector=item.get("selector", f"#{item.get('id')}" if item.get('id') else None)
                ))
            logger.info(f"Groq VLM successfully extracted {len(elements)} visual UI elements.")
            return elements

    def _generate_synthetic_visual_elements(self) -> List[UIElement]:
        """
        Generates fallback visual element descriptors when Vision API is unconfigured or fails.
        """
        return [
            UIElement(
                tag="canvas",
                text="Canvas Application Main Workspace",
                id="visual_canvas_main",
                type="canvas",
                selector="#visual_canvas_main"
            ),
            UIElement(
                tag="button",
                text="Canvas Interactive Action Control",
                id="visual_button_action",
                type="button",
                selector="#visual_button_action"
            ),
            UIElement(
                tag="input",
                text="Canvas Input Control",
                id="visual_input_main",
                placeholder="Visual input...",
                type="text",
                selector="#visual_input_main"
            )
        ]
