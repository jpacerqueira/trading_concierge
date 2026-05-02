#!/usr/bin/env python3
"""
Pre-test environment validation script.
Run this before pytest to ensure all services are available.
"""

import asyncio
import httpx
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(encoding="utf-8")  #
API_BASE_URL = os.getenv("TRADE_API_BASE_URL", "http://localhost:8000")

async def check_trade_api():
    """Check if Trade Blotter API is available"""
    print(f"Checking Trade API at {API_BASE_URL}...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{API_BASE_URL}/health")
            response.raise_for_status()
            data = response.json()
            print(f"  ✅ Trade API is healthy")
            print(f"     Status: {data.get('status', 'N/A')}")
            print(f"     Version: {data.get('version', 'N/A')}")
            return True
    except httpx.ConnectError:
        print(f"  ❌ Cannot connect to Trade API at {API_BASE_URL}")
        print(f"     Make sure the API is running:")
        print(f"       cd ../tradeQueryApi")
        print(f"       uvicorn main:app --reload")
        return False
    except httpx.TimeoutException:
        print(f"  ❌ Trade API timeout at {API_BASE_URL}")
        return False
    except Exception as e:
        print(f"  ❌ Trade API error: {e}")
        return False

def check_mcp_server_script():
    """Check if MCP server script exists"""
    print("Checking MCP server script...")
    script_path = Path("mcp_server.py")
    if script_path.exists():
        print(f"  ✅ mcp_server.py found at {script_path.absolute()}")
        return True
    else:
        print(f"  ❌ mcp_server.py not found")
        print(f"     Expected location: {script_path.absolute()}")
        print(f"     Run this script from the mcp/ directory")
        return False

def check_dependencies():
    """Check if required Python packages are installed"""
    print("Checking Python dependencies...")
    required = {
        "mcp": "1.0.0",
        "httpx": "0.28.1",
        "pytest": "8.0.0",
        "pytest_asyncio": "0.23.0",
        "dotenv": "1.2.1"
    }

    all_installed = True
    for package, _ in required.items():
        try:
            if package == "dotenv":
                __import__("dotenv")
                pkg_name = "python-dotenv"
            elif package == "pytest_asyncio":
                __import__("pytest_asyncio")
                pkg_name = "pytest-asyncio"
            else:
                __import__(package)
                pkg_name = package
            print(f"  ✅ {pkg_name} is installed")
        except ImportError:
            print(f"  ❌ {pkg_name} is NOT installed")
            all_installed = False

    if not all_installed:
        print("\n  Run: pip install -r requirements.txt")

    return all_installed

def check_env_file():
    """Check if .env file exists"""
    print("Checking .env configuration...")
    env_path = Path(".env")
    if env_path.exists():
        print(f"  ✅ .env file found")
        print(f"     TRADE_API_BASE_URL={API_BASE_URL}")
        return True
    else:
        print(f"  ⚠️  .env file not found (optional)")
        print(f"     Using default: {API_BASE_URL}")
        return True

async def main():
    print("="*60)
    print("🔍 MCP Server Test Environment Validation")
    print("="*60)
    print()

    checks = []

    checks.append(check_dependencies())
    print()

    checks.append(check_env_file())
    print()

    checks.append(check_mcp_server_script())
    print()

    checks.append(await check_trade_api())
    print()

    print("="*60)
    if all(checks):
        print("✅ All checks passed! Ready to run pytest")
        print("="*60)
        print()
        print("Run tests with:")
        print("  pytest")
        print("  pytest -v                    # verbose output")
        print("  pytest tests/test_positive.py # specific file")
        return 0
    else:
        print("❌ Some checks failed. Please fix issues above.")
        print("="*60)
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
