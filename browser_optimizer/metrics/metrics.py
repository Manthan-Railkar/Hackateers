import threading
import tiktoken
from typing import Dict, Any

class MetricsTracker:
    def __init__(self):
        self.lock = threading.Lock()
        try:
            self.encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.encoder = None
            
        self.stats = {
            "total_requests": 0,
            "raw_bytes": 0,
            "compressed_bytes": 0,
            "actual_raw_tokens": 0,
            "actual_compressed_tokens": 0,
            "actual_tokens_saved": 0,
            "cache_hits": 0,
            "semantic_hits": 0,
            "cache_misses": 0,
            "actions_executed": 0
        }
        self.last_verification_data = None
        
    def _count_tokens(self, text: str) -> int:
        if self.encoder:
            try:
                return len(self.encoder.encode(text))
            except Exception:
                pass
        return len(text) // 4 # Fallback estimation
        
    def record_extraction(self, raw_html: str, compressed_json: str, is_cache_hit: bool, is_semantic: bool):
        with self.lock:
            self.stats["total_requests"] += 1
            if is_cache_hit:
                self.stats["cache_hits"] += 1
                if is_semantic:
                    self.stats["semantic_hits"] += 1
            else:
                self.stats["cache_misses"] += 1
                
            raw_len = len(raw_html.encode('utf-8'))
            comp_len = len(compressed_json.encode('utf-8'))
            raw_tokens = self._count_tokens(raw_html)
            comp_tokens = self._count_tokens(compressed_json)
            
            self.stats["raw_bytes"] += raw_len
            self.stats["compressed_bytes"] += comp_len
            self.stats["actual_raw_tokens"] += raw_tokens
            self.stats["actual_compressed_tokens"] += comp_tokens
            self.stats["actual_tokens_saved"] += max(0, raw_tokens - comp_tokens)
            
            self.last_verification_data = {
                "raw_html": raw_html[:5000] + "... (truncated)",
                "compressed_json": compressed_json,
                "raw_tokens": raw_tokens,
                "compressed_tokens": comp_tokens,
                "token_reduction_percent": round((1 - comp_tokens / max(1, raw_tokens)) * 100, 2)
            }
            
    def record_action(self):
        with self.lock:
            self.stats["actions_executed"] += 1
            
    def get_metrics(self) -> Dict[str, Any]:
        with self.lock:
            total_raw = max(1, self.stats["actual_raw_tokens"])
            saved = self.stats["actual_tokens_saved"]
            return {
                **self.stats,
                "overall_compression_ratio_percent": round((saved / total_raw) * 100, 2),
                "estimated_cost_savings_usd": round(saved * (0.002 / 1000), 4)
            }

# Global singleton
metrics_tracker = MetricsTracker()
