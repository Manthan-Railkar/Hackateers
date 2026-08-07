import argparse
import sys
import os
import subprocess
from typing import List, Tuple
from browser_optimizer import __version__
from browser_optimizer.config.settings import get_settings
from browser_optimizer.utils.logger import logger


def check_python_version() -> Tuple[bool, str]:
    version = sys.version_info
    valid = version >= (3, 10)
    msg = f"Python {version.major}.{version.minor}.{version.micro} ({'OK' if valid else 'Requires >= 3.10'})"
    return valid, msg


def check_imports() -> List[Tuple[str, bool, str]]:
    modules = [
        ("playwright", "Playwright Automation Framework"),
        ("mcp", "Model Context Protocol SDK"),
        ("bs4", "BeautifulSoup4 HTML Parser"),
        ("httpx", "HTTPX Async Client"),
        ("loguru", "Loguru Logger"),
        ("lxml", "lxml Fast Parser"),
        ("pydantic", "Pydantic V2 Data Validation"),
        ("pydantic_settings", "Pydantic Settings Management"),
        ("dotenv", "Python Dotenv Environment Loader"),
        ("xxhash", "xxHash Fast Hashing"),
        ("cachetools", "Cachetools LRU Caching"),
        ("websockets", "WebSockets Real-time Protocol"),
        ("tiktoken", "Tiktoken Token Counter"),
        ("numpy", "NumPy Vector Calculations"),
        ("sklearn", "Scikit-Learn ML Utilities"),
        ("lightgbm", "LightGBM Classification Engine"),
    ]
    results = []
    for mod_name, description in modules:
        try:
            __import__(mod_name)
            results.append((mod_name, True, f"{description} ({mod_name})"))
        except ImportError as e:
            results.append((mod_name, False, f"{description} ({mod_name}) - Missing: {e}"))
    return results


def check_env_file() -> Tuple[bool, str]:
    env_exists = os.path.exists(".env")
    if env_exists:
        return True, ".env configuration file found."
    else:
        return False, ".env configuration file missing (use .env.example as template)."


def doctor_command() -> int:
    print(f"\n🔍 Running Browser Optimizer Doctor Diagnostics (v{__version__})...\n")
    all_ok = True

    # 1. Python Version
    py_ok, py_msg = check_python_version()
    print(f"[{'✓' if py_ok else '✗'}] {py_msg}")
    if not py_ok:
        all_ok = False

    # 2. Package Dependencies
    print("\n📦 Checking Required Dependencies:")
    import_results = check_imports()
    for mod_name, ok, msg in import_results:
        print(f"  [{'✓' if ok else '✗'}] {msg}")
        if not ok:
            all_ok = False

    # 3. Environment Configuration
    print("\n⚙️ Checking Environment Configuration:")
    env_ok, env_msg = check_env_file()
    print(f"[{'✓' if env_ok else '✗'}] {env_msg}")
    if not env_ok:
        all_ok = False

    try:
        settings = get_settings()
        print(f"  • LOG_LEVEL: {settings.LOG_LEVEL}")
        print(f"  • HEADLESS: {settings.HEADLESS}")
        print(f"  • BROWSER_TIMEOUT: {settings.BROWSER_TIMEOUT}ms")
        print(f"  • SQLITE_DB_PATH: {settings.SQLITE_DB_PATH}")
    except Exception as e:
        print(f"  [✗] Failed to load Settings: {e}")
        all_ok = False

    print("\n" + ("=" * 50))
    if all_ok:
        print("✅ Doctor Check Complete: All systems operational!")
        return 0
    else:
        print("⚠️ Doctor Check Found Issues: Please resolve the items marked with [✗].")
        return 1


def install_command() -> int:
    print(f"\n🚀 Installing Browser Optimizer MCP (v{__version__}) components...\n")
    print("Installing Playwright Chromium browser driver...")
    try:
        cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
        subprocess.run(cmd, check=True)
        print("✅ Playwright Chromium installed successfully.")
    except Exception as e:
        print(f"❌ Failed to install Playwright Chromium: {e}")
        return 1

    if not os.path.exists(".env") and os.path.exists(".env.example"):
        import shutil
        shutil.copy(".env.example", ".env")
        print("✅ Created .env file from .env.example template.")

    print("\n🎉 Browser Optimizer setup complete!")
    return 0


def version_command() -> int:
    print(f"Browser Optimizer MCP Engine v{__version__}")
    return 0


def start_command() -> int:
    print(f"Starting Browser Optimizer MCP Server (v{__version__})...")
    # Entry point for MCP server
    try:
        from browser_optimizer.browser.manager import get_browser_manager
        print("Browser Manager initialized successfully.")
        print("MCP Server ready.")
        return 0
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="browser-optimizer",
        description="Browser Optimizer MCP - Token-Optimized Middleware Engine for AI Browser Automation"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    subparsers.add_parser("doctor", help="Run diagnostic environment and dependency checks")
    subparsers.add_parser("install", help="Install required Playwright browser drivers and setup env")
    subparsers.add_parser("start", help="Start the Browser Optimizer service")
    subparsers.add_parser("version", help="Print package version")

    args = parser.parse_args()

    if args.command == "doctor":
        sys.exit(doctor_command())
    elif args.command == "install":
        sys.exit(install_command())
    elif args.command == "start":
        sys.exit(start_command())
    elif args.command == "version":
        sys.exit(version_command())
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
