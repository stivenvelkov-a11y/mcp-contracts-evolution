# Evolution Contracts API — read-only integration reference

This is a small, code-verified subset of the Contracts API (29 September 2026). Paths are relative; no environment URL or credentials are included. The examples below are synthetic and show only fields relevant to an MCP response, not the complete API DTO.

| Purpose | Endpoint | Notes |
| --- | --- | --- |
| Search | `GET /api/contracts?search=Alfa` | Returns an array. `search` also matches contract number, description, and file name; check `supplierName` if the tool promises supplier-only results. |
| Filter by supplier ID | `GET /api/contracts?supplierId=<id>` | `supplierId` is an identifier, not a supplier name. |
| Filter by status | `GET /api/contracts?status=VALID` | Use actual status values listed below. |
| Detail | `GET /api/contracts/{contractId}` | Returns one contract. |
| Clauses | `GET /api/contracts/{contractId}/clauses` | Returns an array; optional for the first integration. |

Example search response, shortened:

```json
[
  {"id":"demo-001","contractNumber":"A-2026-001","supplierId":"supplier-alfa","supplierName":"Alfa S.p.A.","status":"VALID","description":"Maintenance","startDate":"2026-01-01","endDate":"2026-12-31"},
  {"id":"demo-002","contractNumber":"A-2026-002","supplierId":"supplier-alfa","supplierName":"Alfa S.p.A.","status":"NEGOTIATION","description":"Materials","startDate":null,"endDate":null}
]
```

Example detail is one object from the same shape, possibly with additional fields. Example clauses response:

```json
[{"id":1,"clauseCode":"PAYMENT","clauseType":"commercial","description":"Payment within 30 days"}]
```

Current statuses: `DRAFT`, `PROCESSING`, `NEGOTIATION`, `TO_BE_VALIDATED`, `VALID`, `CLOSE_TO_EXPIRATION`, `EXPIRED`, `OLD_VERSION`. The API's document object exposes metadata but no ready-to-use document URL.

## Integration constraints

- These endpoints require the caller's **read** permission. Tenant and supplier visibility come from the authenticated request, not from model-selected parameters.
- An external supplier user is restricted to its own supplier by the backend, even if a different `supplierId` is requested.
- The list endpoint currently has no pagination and filters the tenant's records in memory. Keep MCP responses small; discuss backend pagination before using large datasets.
- For a local simulation, cover results, an empty search, an unknown ID, denied access, and separation between synthetic tenants. The exact HTTP error mapping for the live environment must be verified with the team.
- The real API URL, test identity, and token flow will be provided after the local integration is reviewed. Do not invent tenant headers or forward an arbitrary bearer token.

## Observable API behaviour

The machine-readable description of the endpoints is in
[contracts-openapi.yaml](contracts-openapi.yaml). Build the simulation from it.

- **Base path:** all endpoints live under a service prefix that is part of the base URL
  (`EVOLUTION_API_BASE_URL`); the code appends only `/api/contracts...`.
- **Authentication:** bearer token. Some deployments also require context headers,
  supplied by the environment: accept them as configuration, never hard-code or invent them.
- **Errors:** JSON body `{"code": "<CODE>", "message": "<text>"}`.
  - 400 `VALIDATION_ERROR` (or `FIELD_VALIDATION_ERROR`, with a `fieldErrors` object)
  - 401 missing or invalid credentials (the body may be empty or not JSON)
  - 403 `FORBIDDEN`
  - 404 `NOT_FOUND`
  - anything else `REQUEST_FAILED`
- **List:** plain JSON array, no pagination, possibly empty. `search` is free text and
  also matches contract number, description and file name; filter by supplier name on the
  tool side if the tool needs to. `status` can be repeated.
- **Detail:** one object. Almost every field can be null; never assume a field is present.
- **Documents:** metadata only, no download URL.
- The error mapping on the live environment is verified separately; the simulation follows
  this list.
