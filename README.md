# Contracts MCP integration

This repository is for a read-only MCP integration with the Evolution Contracts API. Implementation and project structure are intentionally left open.

Start with synthetic data and simulate the API behavior described in [docs/contracts-api.md](docs/contracts-api.md). The intended tools are contract search and contract detail; clause retrieval is optional. Keep the data source replaceable so the same tools can later call the real API without changing their public interface.

The first handoff is a locally demonstrable MCP server and brief run instructions. Connection to a real Evolution environment requires a test endpoint and an approved authentication flow. Synapse integration will be reviewed separately after the API-backed server works.

Do not commit credentials, tokens, customer data, local databases, or environment files.

## Data source

`MCP_intro/server.py` calls the Evolution Contracts API (see [docs/contracts-api.md](docs/contracts-api.md)) through `MCP_intro/api_client.py`. With no configuration the server runs against a local, deterministic simulation with synthetic data. To point it at a real environment, set `EVOLUTION_API_BASE_URL` (and `EVOLUTION_API_TOKEN` once the team provides the approved token flow). `EVOLUTION_SIMULATION_SUPPLIER_ID` optionally restricts the simulation to a single supplier, to exercise the denied-access case. The simulation also ships dedicated ids for the error cases — `denied-001` (HTTP 403), `error-001` (HTTP 500) and `timeout-001` (timeout) — usable with `get_contract`.

## Tests

End-to-end tests live in `MCP_intro/tests/`. They spawn the real server and talk to it over stdio with an MCP client (the same interaction the MCP Inspector performs). From `MCP_intro/`:

```
.venv\Scripts\python -m pytest tests/ -v
```
