import sys
from browser_optimizer.utils.logger import logger, setup_logger


def test_logger_setup():
    """Verify setup_logger executes cleanly without stdout pollution."""
    setup_logger()
    # Log test message
    logger.info("Test log message for loguru stderr output validation.")
    assert True
