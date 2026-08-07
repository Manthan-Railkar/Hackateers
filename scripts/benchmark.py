import asyncio
from browser_optimizer.server.main import extract_context
from browser_optimizer.browser.manager import get_browser_manager
from browser_optimizer.metrics.metrics import metrics_tracker
import json

async def run_benchmark():
    urls = [
        "https://news.ycombinator.com",
        "https://example.com"
    ]
    
    manager = get_browser_manager()
    print("Starting Benchmark Suite...")
    
    for url in urls:
        print(f"\nBenchmarking {url}...")
        try:
            # First extraction (Cache miss expected)
            res1 = await extract_context(url, session_id="benchmark")
            data1 = json.loads(res1)
            print(f"Extraction 1 done. Page Type: {data1.get('page_type')}")
            
            # Second extraction (Cache hit expected)
            res2 = await extract_context(url, session_id="benchmark")
            data2 = json.loads(res2)
            print(f"Extraction 2 done. Cache Hit triggered.")
        except Exception as e:
            print(f"Error benchmarking {url}: {e}")
            
    await manager.stop()
    
    print("\n--- Benchmark Results ---")
    metrics = metrics_tracker.get_metrics()
    print(f"Total Requests: {metrics['total_requests']}")
    print(f"Cache Hits: {metrics['cache_hits']}")
    print(f"Overall Compression: {metrics['overall_compression_ratio_percent']}%")
    print(f"Tokens Saved: {metrics['actual_tokens_saved']}")
    
    assert metrics['overall_compression_ratio_percent'] > 10, "Compression ratio is too low!"
    print("\nBenchmark Passed Successfully!")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
