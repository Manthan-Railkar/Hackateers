"""
Visual fallback module for unreadable / canvas-heavy / SPA web pages.
Captures page screenshots and uses Groq Vision API (Llama 3.2 Vision)
to extract visible interactive elements when DOM parsing fails or yields < 3 elements.
"""

import base64
import json
import httpx
from typing import Dict, List, Any, Optional
from browser_optimizer.config.settings import settings
from browser_optimizer.utils.logger import logger


class VisionAnalyzer:
    """
    Analyzes page screenshots via Groq's multimodal Llama 3.2 Vision model
    or falls back gracefully to synthetic metadata if API key is missing/unreachable.
    """

    async def capture_and_analyze(self, page) -> List[Dict[str, Any]]:
        """
        Take a screenshot of the Playwright page and extract UI elements using Groq Vision API.
        
        Args:
            page (Page): Active Playwright page context.
            
        Returns:
            List[Dict[str, Any]]: List of extracted UI elements from visual analysis.
        """
        logger.info("Triggering Visual Fallback analysis via Playwright screenshot...")
        try:
            # 1. Capture Playwright screenshot as JPEG base64
            screenshot_bytes = await page.screenshot(type="jpeg", quality=70)
            b64_image = base64.b64encode(screenshot_bytes).decode("utf-8")
            data_url = f"data:image/jpeg;base64,{b64_image}"

            # 2. Call Groq API if API key is available
            api_key = settings.GROQ_API_KEY
            if api_key:
                elements = await self._call_groq_vision_api(data_url, api_key)
                if elements:
                    logger.info(f"Visual Fallback extracted {len(elements)} elements from vision model.")
                    return elements

            # 3. Graceful fallback if no API key or API call failed
            logger.warning("Groq API key not set or vision call returned empty. Using heuristic visual fallback.")
            return await self._heuristic_visual_fallback(page)
            
        except Exception as e:
            logger.error(f"Error during Visual Fallback capture_and_analyze: {e}")
            return await self._heuristic_visual_fallback(page)

    async def _call_groq_vision_api(self, data_url: str, api_key: str) -> List[Dict[str, Any]]:
        """
        Call Groq Chat Completions API with multimodal image payload.
        """
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        system_prompt = (
            "You are a web UI vision parser. Analyze the given webpage screenshot. "
            "Identify all visible interactive elements (buttons, input fields, links, search bars, textareas). "
            "Respond ONLY with a valid JSON array of objects. Do not include markdown formatting or extra text outside JSON. "
            "Each object must have the following keys:\n"
            "- \"tag\": element tag type (\"button\", \"input\", \"a\", \"textarea\", \"select\")\n"
            "- \"text\": visible text label or placeholder\n"
            "- \"id\": optional descriptive id or label\n"
            "- \"type\": element input type or \"button\"/\"link\"\n"
            "Example output: [{\"tag\": \"button\", \"text\": \"Submit\", \"id\": \"btn_submit\", \"type\": \"button\"}]"
        )

        payload = {
            "model": settings.GROQ_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": system_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url}
                        }
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1000
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                logger.error(f"Groq API call failed (HTTP {response.status_code}): {response.text}")
                return []

            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            
            # Clean markdown formatting if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            try:
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    normalized = []
                    for item in parsed:
                        if isinstance(item, dict):
                            normalized.append({
                                "tag": str(item.get("tag", "button")),
                                "text": str(item.get("text", "Visual Element")),
                                "id": str(item.get("id", "visual_element")),
                                "name": item.get("name"),
                                "placeholder": item.get("placeholder"),
                                "type": str(item.get("type", "button")),
                                "href": item.get("href"),
                                "visual_fallback": True
                            })
                    return normalized
            except Exception as pe:
                logger.warning(f"Failed to parse JSON response from Groq Vision API: {pe}. Raw output: {content}")
                return []

        return []

    async def _heuristic_visual_fallback(self, page) -> List[Dict[str, Any]]:
        """
        Provides fallback visual elements when Groq Vision API is unreachable or omitted.
        """
        try:
            url_str = page.url
        except Exception:
            url_str = "canvas_page"
        title = url_str.rsplit("/", 1)[-1] or "page"
        return [
            {
                "tag": "button",
                "text": f"Interactive Canvas/Visual Area ({title})",
                "id": "visual_canvas_main",
                "name": None,
                "placeholder": None,
                "type": "button",
                "href": None,
                "visual_fallback": True
            },
            {
                "tag": "input",
                "text": "Search / Action Input",
                "id": "visual_input_main",
                "name": "visual_search",
                "placeholder": "Enter search or command...",
                "type": "text",
                "href": None,
                "visual_fallback": True
            }
        ]


# Shared instance export
vision_analyzer = VisionAnalyzer()
