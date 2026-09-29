# Contracts MCP integration

This repository is for a read-only MCP integration with the Evolution Contracts API. Implementation and project structure are intentionally left open.

Start with synthetic data and simulate the API behavior described in [docs/contracts-api.md](docs/contracts-api.md). The intended tools are contract search and contract detail; clause retrieval is optional. Keep the data source replaceable so the same tools can later call the real API without changing their public interface.

The first handoff is a locally demonstrable MCP server and brief run instructions. Connection to a real Evolution environment requires a test endpoint and an approved authentication flow. Synapse integration will be reviewed separately after the API-backed server works.

Do not commit credentials, tokens, customer data, local databases, or environment files.

## Tests

End-to-end tests live in `MCP_intro/tests/`. They spawn the real server and talk to it over stdio with an MCP client (the same interaction the MCP Inspector performs). From `MCP_intro/`:

```
.venv\Scripts\python -m pytest tests/ -v
```
