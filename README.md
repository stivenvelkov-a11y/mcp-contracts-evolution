# Contracts MCP integration

This repository is for a read-only MCP integration with the Evolution Contracts API. Implementation and project structure are intentionally left open.

Start with synthetic data and simulate the API behavior described in [docs/contracts-api.md](docs/contracts-api.md). The intended tools are contract search and contract detail; clause retrieval is optional. Keep the data source replaceable so the same tools can later call the real API without changing their public interface.

The first handoff is a locally demonstrable MCP server and brief run instructions. Connection to a real Evolution environment requires a test endpoint and an approved authentication flow. Synapse integration will be reviewed separately after the API-backed server works.

Do not commit credentials, tokens, customer data, local databases, or environment files.

## Installation & Setup

1. **Create and activate a virtual environment** (from `MCP_intro/`):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

`requirements.txt` pins only the three direct dependencies:

- `mcp` — the MCP SDK: `MCPServer` in `server.py` and the stdio client used by the tests
- `httpx` — HTTP calls to the real Evolution API in `api_client.py` (not needed for the local simulation)
- `pytest` — runs the end-to-end tests in `MCP_intro/tests/`

## Data source

`MCP_intro/server.py` calls the Evolution Contracts API (see [docs/contracts-api.md](docs/contracts-api.md)) through `MCP_intro/api_client.py`. With no configuration the server runs against a local, deterministic simulation with synthetic data. To point it at a real environment, set `EVOLUTION_API_BASE_URL` (and `EVOLUTION_API_TOKEN` once the team provides the approved token flow). `EVOLUTION_SIMULATION_SUPPLIER_ID` optionally restricts the simulation to a single supplier, to exercise the denied-access case. The simulation also ships dedicated ids for the error cases — `denied-001` (HTTP 403), `error-001` (HTTP 500) and `timeout-001` (timeout) — usable with `get_contract`.

## Tests

End-to-end tests live in `MCP_intro/tests/`. They spawn the real server and talk to it over stdio with an MCP client (the same interaction the MCP Inspector performs). From `MCP_intro/`:

```
.venv\Scripts\python -m pytest tests/ -v
```

## MCP Inspector

For manual checking, the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) (the official browser-based MCP developer tool) can drive the server the same way the tests do: list the tools, call them, and inspect the raw requests and responses. It requires Node.js (>= 22.19). From `MCP_intro/`:

```
npx @modelcontextprotocol/inspector .venv\Scripts\python server.py
```

The web UI opens at `http://localhost:6274`. Connect to the spawned server, then use the **Tools** tab to list and call `search_contract` and `get_contract`.