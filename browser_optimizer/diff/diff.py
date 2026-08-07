from typing import List, Dict, Set
from browser_optimizer.schemas.schemas import UIElement, PageDiff
from browser_optimizer.utils.logger import logger

class StateDifferenceEngine:
    def __init__(self):
        self.history: Dict[str, Dict[str, UIElement]] = {}
        
    def _fingerprint(self, element: UIElement) -> str:
        # tag|id|name|text[:30]|placeholder
        text_preview = element.text[:30].replace("\n", " ").strip()
        return f"{element.tag}|{element.id}|{element.name}|{text_preview}|{element.placeholder}"
        
    def compute_diff(self, url: str, current_elements: List[UIElement]) -> PageDiff:
        current_map = {self._fingerprint(el): el for el in current_elements}
        
        if url not in self.history:
            self.history[url] = current_map
            return PageDiff(url=url, added=current_elements, removed=[], changed=[])
            
        previous_map = self.history[url]
        
        current_keys = set(current_map.keys())
        previous_keys = set(previous_map.keys())
        
        added_keys = current_keys - previous_keys
        removed_keys = previous_keys - current_keys
        
        added = [current_map[k] for k in added_keys]
        removed = [previous_map[k] for k in removed_keys]
        
        self.history[url] = current_map
        
        logger.debug(f"Computed diff for {url}: {len(added)} added, {len(removed)} removed")
        return PageDiff(url=url, added=added, removed=removed, changed=[])
