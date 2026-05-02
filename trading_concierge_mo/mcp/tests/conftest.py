import pytest
import asyncio
import os
import httpx
import sys
from pathlib import Path

# Ensure src/mcp is importable when running tests from repo root
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

@pytest.fixture(scope="session")
def event_loop_policy():
    """Use the default event loop policy"""
    return asyncio.DefaultEventLoopPolicy()

@pytest.fixture(scope="function")
def event_loop(event_loop_policy):
    """Create new event loop for each test"""
    loop = event_loop_policy.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def project_root():
    """Get the mcp directory regardless of where pytest is invoked from"""
    return Path(__file__).parent.parent

@pytest.fixture(scope="session")
def workspace_root():
    """Get the workspace root (MCP_Test directory)"""
    return Path(__file__).parent.parent.parent.parent

@pytest.fixture(scope="session")
def api_base_url():
    """Trade API base URL from environment"""
    return os.getenv("TRADE_API_BASE_URL", "http://localhost:8000")

@pytest.fixture(scope="session")
def mcp_server_script(project_root):
    """Get absolute path to mcp_server.py"""
    return str(project_root / "mcp_server.py")

@pytest.fixture(scope="session")
def trade_api_path(workspace_root):
    """Get path to tradeQueryApi component"""
    return workspace_root / "src" / "tradeQueryApi"

@pytest.fixture(scope="session")
async def check_trade_api(api_base_url):
    """Check if Trade Blotter API is available before running tests"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{api_base_url}/health")
            response.raise_for_status()
            print(f"\nOK: Trade API is available at {api_base_url}")
            return True
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError) as e:
        pytest.exit(
            f"\n\n"
            f"{'='*60}\n"
            f"❌ Trade Blotter API is not available at {api_base_url}\n"
            f"{'='*60}\n"
            f"Error: {str(e)}\n\n"
            f"Please start the Trade API before running MCP tests:\n\n"
            f"  Option 1 - From project root:\n"
            f"    cd src/tradeQueryApi\n"
            f"    uvicorn main:app --reload\n\n"
            f"  Option 2 - From tradeQueryApi directory:\n"
            f"    uvicorn main:app --reload\n\n"
            f"Then verify it's running:\n"
            f"  curl {api_base_url}/health\n\n"
            f"{'='*60}\n",
            returncode=1
        )

@pytest.fixture(scope="session")
def verify_mcp_server_script(mcp_server_script):
    """Verify MCP server script exists"""
    script_path = Path(mcp_server_script)
    if not script_path.exists():
        pytest.exit(
            f"\n\n"
            f"{'='*60}\n"
            f"❌ MCP server script not found\n"
            f"{'='*60}\n"
            f"Expected: {script_path.absolute()}\n"
            f"Current working directory: {Path.cwd()}\n\n"
            f"Ensure you're running from the correct directory.\n"
            f"{'='*60}\n",
            returncode=1
        )
    print(f"✓ MCP server script: {script_path.name}")
    return str(script_path)

@pytest.fixture(autouse=True)
def env_setup(monkeypatch, project_root):
    """Setup environment and working directory for all tests"""
    monkeypatch.setenv("TRADE_API_BASE_URL", os.getenv("TRADE_API_BASE_URL", "http://localhost:8000"))

    original_cwd = Path.cwd()
    os.chdir(project_root)

    yield

    os.chdir(original_cwd)

@pytest.fixture(scope="session", autouse=True)
def validate_test_environment(check_trade_api, verify_mcp_server_script, workspace_root):
    """Validate entire test environment before running any tests"""
    print("\n" + "="*60)
    print("MCP Server Test Environment")
    print("="*60)
    print(f"Workspace: {workspace_root}")
    print(f"Component: src/mcp/")
    print(f"Shared .venv: {workspace_root / '.venv'}")
    print("="*60)
    print("OK: All prerequisites met - starting MCP tests")
    print("="*60 + "\n")

def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "requires_api: mark test as requiring Trade API")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "unit: mark test as unit test")

def pytest_collection_modifyitems(config, items):
    """Auto-mark async tests and add markers based on test names"""
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)

        if "call_tool" in item.name:
            item.add_marker(pytest.mark.requires_api)

        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)

def pytest_sessionstart(session):
    """Print environment info at session start"""
    print("\n" + "="*60)
    print("Test Configuration")
    print("="*60)
    print(f"Python: {os.sys.version.split()[0]}")
    print(f"Pytest Root: {session.config.rootpath}")
    print(f"Working Directory: {os.getcwd()}")
    print(f"TRADE_API_BASE_URL: {os.getenv('TRADE_API_BASE_URL', 'http://localhost:8000')}")
    print("="*60)

def pytest_sessionfinish(session, exitstatus):
    """Print summary at session end"""
    print()
    if exitstatus == 0:
        print("OK: All MCP tests passed successfully!")
    elif exitstatus == 1:
        print("ERROR: Some MCP tests failed")
    else:
        print(f"WARNING: MCP tests finished with status: {exitstatus}")
