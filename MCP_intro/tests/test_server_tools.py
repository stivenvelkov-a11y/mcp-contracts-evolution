"""Automatic tests of the MCP server in server.py.

Each test starts the real server (``python server.py``) as a
subprocess and queries it on stdio with an MCP client: the same
interaction that the MCP Inspector performs, but scripted and
repeatable.

The server uses the client in api_client.py; the tests assume the
local simulation with synthetic data (no EVOLUTION_API_BASE_URL).

Checks covered:
- ``search_contract`` returns the results with a search that
  matches known suppliers (also case-insensitively) and only the
  contracts of the searched supplier;
- ``search_contract`` returns an empty list with a search
  that has no matches;
- ``get_contract`` returns the full detail with a valid id;
- ``get_contract`` raises a ToolError (is_error=True) with a nonexistent id;
- ``get_contract`` raises a ToolError for access denied (id ``denied-001``);
- ``get_contract`` raises a ToolError if the API fails with HTTP 500
  (id ``error-001``) or times out (id ``timeout-001``);
- ``search_contract`` raises a ToolError when passed an empty supplier name.

Running (from the MCP_intro folder):
    python -m pytest tests/ -v
"""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# Project root: the folder containing server.py
ROOT = Path(__file__).resolve().parent.parent
SERVER_PATH = ROOT / "server.py"

# Ensures the import of api_client even if pytest does not put the
# project root in sys.path.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_client import SimulatedContractsApi

TOOL_SEARCH = "search_contract"
TOOL_DETAIL = "get_contract"

# Timeout in seconds for each single request to the server
TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _session():
    """Starts the server as a subprocess and opens an MCP client session."""
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        cwd=ROOT,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def _with_session(scenario) -> None:
    """Runs an async scenario on a single server session."""
    async with _session() as session:
        await scenario(session)


def _run(scenario) -> None:
    """Runs a scenario in a new event loop (pytest without the async plugin)."""
    asyncio.run(_with_session(scenario))


def _payload(result):
    """Extracts the payload returned by the tool from a successful CallToolResult."""
    assert not result.is_error, (
        f"Expected tool success, but got an error: {result.content}"
    )
    if result.structured_content is not None:
        content = result.structured_content
        # The server wraps the payload in a "result" field.
        if isinstance(content, dict) and set(content) == {"result"}:
            return content["result"]
        return content
    # Fallback: the result is serialized as JSON text.
    assert len(result.content) == 1
    text = json.loads(result.content[0].text)
    if isinstance(text, dict) and set(text) == {"result"}:
        return text["result"]
    return text


def _error_text(result) -> str:
    """Extracts error text from a failed CallToolResult (is_error == True)."""
    assert result.is_error, "Expected tool execution to fail (is_error=True), but it succeeded."
    assert len(result.content) > 0, "Tool error result has no content."
    return result.content[0].text


def _total_contracts() -> int:
    """Total number of contracts visible in the local simulation."""
    return len(SimulatedContractsApi().list_contracts())


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


async def _scenario_tools_exposed(session):
    """The two tools are visible to the inspector in the tool list."""
    listing = await session.list_tools()
    names = {tool.name for tool in listing.tools}
    assert {TOOL_SEARCH, TOOL_DETAIL} <= names, f"missing tools: {names}"


async def _scenario_search_with_results(session):
    res = _payload(await session.call_tool(TOOL_SEARCH, {"supplier_name": "ALFA"}))

    assert isinstance(res, list), f"unexpected result: {res!r}"
    assert len(res) > 0, "the search for a known supplier did not return contracts"
    for contract in res:
        assert {"id", "number", "supplier_name", "status"} <= set(contract)
        assert "alfa" in contract["supplier_name"].lower()

    # The search is case-insensitive
    res_beta = _payload(await session.call_tool(TOOL_SEARCH, {"supplier_name": "beta"}))
    assert isinstance(res_beta, list) and len(res_beta) > 0
    assert all("beta" in c["supplier_name"].lower() for c in res_beta)


async def _scenario_search_without_results(session):
    res = _payload(
        await session.call_tool(TOOL_SEARCH, {"supplier_name": "ZZZ-NONEXISTENT"})
    )
    assert isinstance(res, list), f"unexpected result: {res!r}"
    assert res == [], "a search with no matches must return an empty list"


async def _scenario_detail_with_valid_id(session):
    found = _payload(await session.call_tool(TOOL_SEARCH, {"supplier_name": "ALFA"}))
    assert isinstance(found, list) and len(found) > 0
    reference = found[0]

    detail = _payload(await session.call_tool(TOOL_DETAIL, {"id": reference["id"]}))
    assert isinstance(detail, dict), f"unexpected result: {detail!r}"
    assert detail["id"] == reference["id"]
    assert detail["number"] == reference["number"]
    assert detail["supplier_name"] == reference["supplier_name"]
    assert detail["status"] == reference["status"]
    
    for field in ("supplier_id", "description", "start_date", "end_date"):
        assert field in detail, f"the field {field!r} is missing from the detail"


async def _scenario_detail_with_nonexistent_id(session):
    result = await session.call_tool(TOOL_DETAIL, {"id": "nonexistent"})
    err = _error_text(result)
    assert "No contract with id" in err


async def _scenario_access_denied(session):
    """The protected contract (denied-001) returns a denied-access ToolError."""
    result = await session.call_tool(TOOL_DETAIL, {"id": "denied-001"})
    err = _error_text(result)
    assert "Access denied" in err, f"unexpected error message: {err!r}"


async def _scenario_api_error(session):
    """The contract simulating internal error (error-001) returns HTTP 500 error."""
    result = await session.call_tool(TOOL_DETAIL, {"id": "error-001"})
    err = _error_text(result)
    assert "HTTP 500" in err, f"unexpected error message: {err!r}"


async def _scenario_timeout(session):
    """The contract simulating timeout (timeout-001) returns timeout error."""
    result = await session.call_tool(TOOL_DETAIL, {"id": "timeout-001"})
    err = _error_text(result)
    assert "timeout" in err.lower(), f"unexpected error message: {err!r}"


async def _scenario_empty_supplier_name(session):
    """An empty supplier name must raise a ToolError."""
    for name in ("", "   "):
        result = await session.call_tool(TOOL_SEARCH, {"supplier_name": name})
        err = _error_text(result)
        assert "supplier_name cannot be empty" in err


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_tools_exposed():
    _run(_scenario_tools_exposed)


def test_search_with_results():
    _run(_scenario_search_with_results)


def test_search_without_results():
    _run(_scenario_search_without_results)


def test_detail_with_valid_id():
    _run(_scenario_detail_with_valid_id)


def test_detail_with_nonexistent_id():
    _run(_scenario_detail_with_nonexistent_id)


def test_access_denied():
    _run(_scenario_access_denied)


def test_api_error():
    _run(_scenario_api_error)


def test_timeout():
    _run(_scenario_timeout)


def test_empty_supplier_name_does_not_return_all():
    _run(_scenario_empty_supplier_name)