"""Read-only MCP server for the Evolution Contracts API.

Exposes two tools:
- search_contract: searches a supplier's contracts by name and
  returns the contracts found with id, number, supplier_name and status.
- get_contract: returns the full detail of a contract, given its id.

The API calls are centralized in api_client.py, which
implements the endpoints of docs/contracts-api.md. If
EVOLUTION_API_BASE_URL is not set, a local simulation with
synthetic data is used (see the api_client module for details).

Start (stdio transport):
    python server.py

Example client-side configuration (Claude Desktop, OpenCode, etc.):
    {
        "mcpServers": {
            "contracts": {
                "command": "python",
                "args": ["C:/path/to/MCP_intro/server.py"]
            }
        }
    }
"""

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from api_client import ApiError, contract_for_tool, create_client, detail_for_tool

mcp = MCPServer("contracts")

# Active API client (real or simulation, chosen by api_client.create_client)
client = create_client()


def format_api_error(exc: ApiError, operation: str) -> str:
    """Helper to convert API status codes into user-friendly error messages.

    The 404 is handled by the individual tools with a more
    specific message (e.g. "No contract with id ...").
    """
    if exc.status == 403:
        detail = "Access denied"
    elif exc.status == 0:
        detail = "Timeout or network error"
    else:
        detail = f"API error (HTTP {exc.status})"
    return f"{detail} during {operation}: {exc.message}"


@mcp.tool()
def search_contract(supplier_name: str) -> list[dict]:
    """Searches a supplier's contracts by name (partial match, case-insensitive).

    Returns the list of contracts found with id, number,
    supplier_name and status. If no row matches, an empty list is returned.

    Raises ToolError if the supplier_name is empty or if the API call fails.
    """
    name = supplier_name.strip()
    if not name:
        raise ToolError("supplier_name cannot be empty")
    try:
        results = client.search_contracts(name)
    except ApiError as exc:
        raise ToolError(format_api_error(exc, "the search"))

    # The API's `search` also matches number, description and file:
    # to keep the tool's promise (supplier name only),
    # only the contracts whose supplier name matches are kept
    # (see docs/contracts-api.md).
    return [
        contract_for_tool(c)
        for c in results
        if name.lower() in c["supplierName"].lower()
    ]


@mcp.tool()
def get_contract(id: str) -> dict:
    """Returns the full detail of a contract, given its id.

    Raise a tool error if the id is empty or if no contract is found.
    """
    contract_id = id.strip()
    if not contract_id:
        raise ToolError("id cannot be empty")
    try:
        record = client.get_contract_detail(contract_id)
    except ApiError as exc:
        if exc.status == 404:
            raise ToolError(f"No contract with id {id}")
    
        raise ToolError(format_api_error(exc, "the detail retrieval"))

    return detail_for_tool(record)


if __name__ == "__main__":
    mcp.run()
