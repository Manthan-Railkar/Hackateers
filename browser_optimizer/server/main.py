import asyncio
from typing import Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

from browser_optimizer.browser.manager import get_browser_manager
from browser_optimizer.extractor.extractor import PageExtractor
from browser_optimizer.compressor.compressor import ContextCompressor
from browser_optimizer.config.settings import get_settings
from browser_optimizer.utils.logger import logger

# Initialize FastMCP Server
mcp = FastMCP("Browser Optimization MCP")

extractor = PageExtractor()
compressor = ContextCompressor()
browser_manager = get_browser_manager()


@mcp.tool()
async def extract_context(url: str, session_id: str = "default") -> str:
    """
    Navigates to URL, perceives page structure, applies DOM pruning,
    and returns compressed JSON payload.
    """
    logger.info(f"MCP Tool extract_context called for URL: '{url}', Session: '{session_id}'")
    page = await browser_manager.navigate(url, session_id=session_id)
    raw_html, soup, ax_tree, visual_elements = await extractor.extract_page_data(page)
    title = await page.title()
    context = compressor.compress(
        raw_html=raw_html,
        soup=soup,
        url=url,
        title=title,
        ax_tree=ax_tree,
        visual_elements=visual_elements
    )
    return context.model_dump_json(exclude_none=True)


@mcp.tool()
async def execute_action(action: str, selector: Optional[str] = None, value: Optional[str] = None, session_id: str = "default") -> Dict[str, Any]:
    """
    Executes a browser interaction action (click, fill, select, scroll, navigate) on target session.
    """
    logger.info(f"MCP Tool execute_action: action='{action}', selector='{selector}', session='{session_id}'")
    page = await browser_manager.get_page(session_id=session_id)

    try:
        if action == "click":
            if not selector:
                return {"success": False, "error": "Selector required for click action"}
            await page.wait_for_selector(selector, timeout=get_settings().BROWSER_TIMEOUT)
            await page.click(selector)
        elif action == "fill":
            if not selector or value is None:
                return {"success": False, "error": "Selector and value required for fill action"}
            await page.wait_for_selector(selector, timeout=get_settings().BROWSER_TIMEOUT)
            await page.fill(selector, value)
        elif action == "select":
            if not selector or value is None:
                return {"success": False, "error": "Selector and value required for select action"}
            await page.select_option(selector, value)
        elif action == "navigate":
            if not value:
                return {"success": False, "error": "URL value required for navigate action"}
            await browser_manager.navigate(value, session_id=session_id)
        else:
            return {"success": False, "error": f"Unsupported action type: '{action}'"}

        await browser_manager.save_session(session_id=session_id)
        return {"success": True, "message": f"Action '{action}' executed successfully."}
    except Exception as e:
        logger.error(f"Action '{action}' failed: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def summarize_page(url: str, session_id: str = "default") -> Dict[str, Any]:
    """
    Generates a quick summary of key UI interactive elements on page.
    """
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
async def get_metrics() -> Dict[str, Any]:
    """
    Returns system status and active configuration settings.
    """
    settings = get_settings()
    return {
        "active_sessions_count": len(browser_manager.sessions),
        "headless": settings.HEADLESS,
        "sqlite_db": settings.SQLITE_DB_PATH,
        "browser_timeout": settings.BROWSER_TIMEOUT
    }


def run_server():
    """
    Starts FastMCP stdio server loop.
    """
    logger.info("Starting Browser Optimizer FastMCP Server...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
