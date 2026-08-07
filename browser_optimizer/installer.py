import sys
import os
import json
import subprocess
from browser_optimizer.utils.logger import logger

def check_python_version():
    if sys.version_info < (3, 10):
        logger.error("Python 3.10 or higher is required.")
        sys.exit(1)
    logger.info(f"Python version check passed: {sys.version}")

def install_playwright_browsers():
    logger.info("Installing Playwright Chromium browser...")
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Playwright browser installation failed: {e}")
        sys.exit(1)

def detect_and_configure_antigravity():
    logger.info("Configuring Gemini/Antigravity MCP...")
    home = os.path.expanduser("~")
    gemini_dir = os.path.join(home, ".gemini", "config")
    mcp_config = os.path.join(gemini_dir, "mcp_config.json")
    
    if not os.path.exists(gemini_dir):
        logger.info("Gemini config directory not found. Skipping.")
        return
        
    config = {}
    if os.path.exists(mcp_config):
        with open(mcp_config, "r") as f:
            try:
                config = json.load(f)
            except Exception:
                config = {}
                
    if "mcpServers" not in config:
        config["mcpServers"] = {}
        
    config["mcpServers"]["browser-optimizer"] = {
        "command": sys.executable,
        "args": ["-m", "browser_optimizer.cli", "start"]
    }
    
    with open(mcp_config, "w") as f:
        json.dump(config, f, indent=2)
    logger.info(f"Updated {mcp_config}")

def detect_and_configure_claude():
    # Stub for claude config
    logger.info("Claude desktop config check skipped.")

def print_cursor_instructions():
    logger.info("For Cursor IDE, manually add this MCP Server using type 'stdio':")
    logger.info(f"Command: {sys.executable} -m browser_optimizer.cli start")

def verify_installation():
    logger.info("Verifying package imports...")
    try:
        import playwright
        import lightgbm
        import bs4
        import numpy
        import tiktoken
        import mcp
        logger.info("All dependencies verified successfully.")
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        sys.exit(1)

def run_installer():
    check_python_version()
    install_playwright_browsers()
    detect_and_configure_antigravity()
    detect_and_configure_claude()
    print_cursor_instructions()
    verify_installation()
    logger.info("Browser Optimizer installation complete!")
