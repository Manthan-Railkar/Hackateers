import sys
from loguru import logger
from browser_optimizer.config.settings import get_settings


def setup_logger() -> None:
    """
    Configures loguru logger to output strictly to sys.stderr.
    This guarantees sys.stdout remains 100% clean for MCP stdio JSON-RPC protocol traffic.
    """
    settings = get_settings()
    logger.remove()  # Remove default handlers
    
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    
    logger.add(
        sys.stderr,
        format=log_format,
        level=settings.LOG_LEVEL.upper(),
        colorize=True,
        backtrace=True,
        diagnose=True,
    )


# Run setup immediately upon import
setup_logger()

__all__ = ["logger", "setup_logger"]
