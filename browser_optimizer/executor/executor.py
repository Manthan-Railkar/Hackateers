from typing import Dict, Any, List
from playwright.async_api import Page
from browser_optimizer.schemas.schemas import ActionResult
from browser_optimizer.utils.logger import logger
from browser_optimizer.config.settings import get_settings

class RuleBasedExecutor:
    def __init__(self):
        self.settings = get_settings()
        self.recordings: Dict[str, List[Dict[str, Any]]] = {}
        self.active_recording: Dict[str, bool] = {}
        
    def start_recording(self, session_id: str):
        self.recordings[session_id] = []
        self.active_recording[session_id] = True
        logger.info(f"Started recording for session {session_id}")
        
    def stop_recording(self, session_id: str) -> List[Dict[str, Any]]:
        self.active_recording[session_id] = False
        logger.info(f"Stopped recording for session {session_id}")
        return self.recordings.get(session_id, [])
        
    async def execute_action(self, page: Page, action: str, selector: str, value: str = "", session_id: str = "") -> ActionResult:
        try:
            logger.debug(f"Executing action '{action}' on '{selector}' with value '{value}'")
            
            if self.active_recording.get(session_id, False):
                self.recordings[session_id].append({
                    "action": action,
                    "selector": selector,
                    "value": value
                })
                
            if action == "navigate":
                await page.goto(selector, wait_until="domcontentloaded", timeout=self.settings.BROWSER_TIMEOUT)
            elif action == "click":
                await page.wait_for_selector(selector, state="visible", timeout=self.settings.BROWSER_TIMEOUT)
                await page.click(selector)
            elif action == "type" or action == "fill":
                await page.wait_for_selector(selector, state="visible", timeout=self.settings.BROWSER_TIMEOUT)
                await page.fill(selector, value)
            elif action == "select":
                await page.wait_for_selector(selector, state="visible", timeout=self.settings.BROWSER_TIMEOUT)
                await page.select_option(selector, value=value)
            elif action == "scroll":
                scroll_amount = int(value) if value else 500
                await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            elif action == "wait":
                wait_time = int(value) if value else 1000
                await page.wait_for_timeout(wait_time)
            else:
                return ActionResult(success=False, message=f"Unknown action: {action}")
                
            return ActionResult(success=True, message="Action executed successfully")
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return ActionResult(success=False, message=str(e))
