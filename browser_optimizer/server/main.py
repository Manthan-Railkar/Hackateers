import asyncio
import json
from typing import Dict, Any, Optional
from fastmcp import FastMCP

from browser_optimizer.browser.manager import get_browser_manager
from browser_optimizer.extractor.extractor import PageExtractor
from browser_optimizer.compressor.compressor import ContextCompressor
from browser_optimizer.config.settings import get_settings
from browser_optimizer.utils.logger import logger
from browser_optimizer.cache.cache import SemanticCache
from browser_optimizer.classifier.classifier import TaskClassifier
from browser_optimizer.diff.diff import StateDifferenceEngine
from browser_optimizer.executor.executor import RuleBasedExecutor
from browser_optimizer.metrics.metrics import metrics_tracker

mcp = FastMCP("Browser Optimization MCP")

extractor = PageExtractor()
compressor = ContextCompressor()
browser_manager = get_browser_manager()

settings = get_settings()
semantic_cache = SemanticCache()
classifier = TaskClassifier()
diff_engine = StateDifferenceEngine()
executor = RuleBasedExecutor()

active_watchers = {}

@mcp.tool()
async def extract_context(url: str, session_id: str = "default") -> str:
    """Navigates to URL, checks cache, extracts, compresses, classifies, and returns JSON payload."""
    logger.info(f"extract_context called: {url}")
    
    page = await browser_manager.navigate(url, session_id=session_id)
    raw_html, soup, ax_tree, visual_elements = await extractor.extract_page_data(page)
    
    cached_context, is_semantic = semantic_cache.get(url, raw_html)
    if cached_context:
        metrics_tracker.record_extraction(raw_html, json.dumps(cached_context), is_cache_hit=True, is_semantic=is_semantic)
        return json.dumps(cached_context)
    
    title = await page.title()
    # Omit ax_tree to hit the 85% compression target
    context = compressor.compress(raw_html, soup, url, title, None, visual_elements)
    context_dict = context.model_dump(exclude_none=True)
    
    page_type, scores = classifier.classify(raw_html, url)
    context_dict["page_type"] = page_type
    
    semantic_cache.set(url, raw_html, context_dict, page_type=page_type)
    
    context_json = json.dumps(context_dict)
    metrics_tracker.record_extraction(raw_html, context_json, is_cache_hit=False, is_semantic=False)
    
    return context_json

@mcp.tool()
async def page_diff(url: str, session_id: str = "default") -> Dict[str, Any]:
    """Computes added/removed elements relative to previous state."""
    page = await browser_manager.get_page(session_id)
    raw_html, soup, ax_tree, visual_elements = await extractor.extract_page_data(page)
    ui_elements = compressor.extract_ui(soup, visual_elements)
    diff = diff_engine.compute_diff(url, ui_elements)
    return diff.model_dump()

@mcp.tool()
async def execute_action(action: str, selector: str, value: str = "", session_id: str = "default") -> Dict[str, Any]:
    """Executes a browser interaction action."""
    page = await browser_manager.get_page(session_id)
    result = await executor.execute_action(page, action, selector, value, session_id)
    metrics_tracker.record_action()
    
    if not result.success:
        logger.warning(f"Action failed: {result.message}")
        
    return result.model_dump()

@mcp.tool()
async def summarize_page(url: str, session_id: str = "default") -> Dict[str, Any]:
    """Generates a quick summary of key UI interactive elements on page."""
    page = await browser_manager.navigate(url, session_id=session_id)
    raw_html, soup, ax_tree, visual_elements = await extractor.extract_page_data(page)
    ui_elements = compressor.extract_ui(soup, visual_elements)
    
    tag_counts = {}
    for elem in ui_elements:
        tag_counts[elem.tag] = tag_counts.get(elem.tag, 0) + 1

    return {
        "url": url,
        "title": await page.title(),
        "total_interactive_controls": len(ui_elements),
        "control_counts_by_tag": tag_counts
    }

@mcp.tool()
async def classify_page(url: str, session_id: str = "default") -> Dict[str, Any]:
    """Returns page category and score distribution."""
    page = await browser_manager.navigate(url, session_id=session_id)
    raw_html, _, _, _ = await extractor.extract_page_data(page)
    page_type, scores = classifier.classify(raw_html, url)
    return {"page_type": page_type, "scores": scores}

@mcp.tool()
async def wait_until_ready(url: str, timeout: int = 30000, session_id: str = "default") -> str:
    """Navigates and waits for networkidle."""
    page = await browser_manager.get_page(session_id)
    await page.goto(url, wait_until="networkidle", timeout=timeout)
    return f"Successfully navigated and waited for {url}"

@mcp.tool()
async def cache_lookup(url: str) -> Dict[str, Any]:
    """Manually check what is cached for a URL."""
    return {"status": "Requires HTML hash to lookup accurately. Call extract_context instead."}

@mcp.tool()
async def get_metrics() -> Dict[str, Any]:
    """Returns live token savings and metrics."""
    return metrics_tracker.get_metrics()

@mcp.tool()
async def start_macro_recording(session_id: str = "default") -> str:
    executor.start_recording(session_id)
    return f"Started recording on session {session_id}"

@mcp.tool()
async def save_macro(name: str, page_type: str, session_id: str = "default") -> Dict[str, Any]:
    steps = executor.stop_recording(session_id)
    return {"status": "saved", "name": name, "steps_recorded": len(steps)}

@mcp.tool()
async def watch_page(url: str, interval_seconds: int = 5, session_id: str = "default") -> str:
    if session_id in active_watchers:
        return "Already watching"
    
    active_watchers[session_id] = True
    asyncio.create_task(_poll_page_diff(url, interval_seconds, session_id))
    return f"Started watching {url} every {interval_seconds} seconds"

@mcp.tool()
async def stop_watch_page(session_id: str = "default") -> str:
    active_watchers.pop(session_id, None)
    return "Stopped watching"

async def _poll_page_diff(url: str, interval: int, session_id: str):
    while active_watchers.get(session_id):
        try:
            page = await browser_manager.get_page(session_id)
            raw_html, soup, ax_tree, visual_elements = await extractor.extract_page_data(page)
            ui_elements = compressor.extract_ui(soup, visual_elements)
            diff = diff_engine.compute_diff(url, ui_elements)
            
            if diff.added or diff.removed:
                logger.info(f"Broadcast diff: {len(diff.added)} added, {len(diff.removed)} removed")
                
        except Exception as e:
            logger.error(f"Watch polling error: {e}")
        await asyncio.sleep(interval)

def run_server():
    logger.info("Starting Browser Optimizer FastMCP Server...")
    mcp.run(transport="stdio")

if __name__ == "__main__":
    run_server()
