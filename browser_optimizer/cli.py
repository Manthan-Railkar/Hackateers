import argparse
import sys
import asyncio
from browser_optimizer.utils.logger import logger
from browser_optimizer.installer import run_installer, verify_installation
from browser_optimizer.server.main import run_server
from browser_optimizer.dashboard.server import start_dashboard

def doctor_cmd():
    verify_installation()
    logger.info("System is healthy.")

def start_cmd():
    logger.info("Starting Dashboard and FastMCP server...")
    start_dashboard()
    run_server()

def install_cmd():
    run_installer()

def version_cmd():
    logger.info("Browser Optimizer MCP v2.0.0")

def main():
    parser = argparse.ArgumentParser(description="Browser Optimizer CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("install", help="Run the full setup wizard")
    subparsers.add_parser("doctor", help="Run diagnostic environment checks")
    subparsers.add_parser("start", help="Launch the MCP server and Dashboard")
    subparsers.add_parser("version", help="Print version")
    
    args = parser.parse_args()
    
    if args.command == "install":
        install_cmd()
    elif args.command == "doctor":
        doctor_cmd()
    elif args.command == "start":
        start_cmd()
    elif args.command == "version":
        version_cmd()
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
