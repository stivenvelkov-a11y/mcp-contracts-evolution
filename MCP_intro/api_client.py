"""Read-only client for the Evolution Contracts API.

Implements the endpoints described in docs/contracts-api.md:

- ``GET /api/contracts?search=<text>``          (search)
- ``GET /api/contracts?supplierId=<id>``        (filter by supplier id)
- ``GET /api/contracts?status=<status>``        (filter by status)
- ``GET /api/contracts/{contractId}``           (detail)
- ``GET /api/contracts/{contractId}/clauses``   (clauses, optional)

Two interchangeable backends, chosen based on the environment, so the
same server can switch to the real API without changing
the public interface of the tools (see README):

- ``HttpContractsApi``: HTTP calls to the real API, used when
  ``EVOLUTION_API_BASE_URL`` is set (the URL and the token flow
  will be provided by the team after the local integration
  review; no tenant headers are invented).
- ``SimulatedContractsApi``: deterministic local simulation with
  synthetic data that mirrors the documentation examples and
  covers the cases requested for local testing: results, empty
  search, unknown id, denied access, internal API error,
  timeout and separation between synthetic tenants. To exercise the
  error cases, use ``get_contract`` with these dedicated ids (also
  visible in search under the supplier "Delta S.p.A."):

  - ``denied-001``  -> denied access (HTTP 403);
  - ``error-001``   -> internal API error (HTTP 500);
  - ``timeout-001`` -> call timeout (no response in time).

Environment variables (all optional):
- ``EVOLUTION_API_BASE_URL``: base URL of the real API (e.g. https://environment.evolution).
- ``EVOLUTION_API_TOKEN``: bearer token, only if explicitly
  configured (the flow will be confirmed with the team).
- ``EVOLUTION_SIMULATION_SUPPLIER_ID``: in the simulation, restricts
  visibility to the given supplier (external user).
"""

from __future__ import annotations

import os
from typing import Protocol
from urllib.parse import quote

import httpx

# Environment variables
ENV_BASE_URL = "EVOLUTION_API_BASE_URL"
ENV_TOKEN = "EVOLUTION_API_TOKEN"
ENV_SIMULATION_SUPPLIER = "EVOLUTION_SIMULATION_SUPPLIER_ID"

# Timeout in seconds for the HTTP calls
TIMEOUT_DEFAULT = 10.0


class ApiError(Exception):
    """Error returned by the API (simulated or real)."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message


class ContractsApi(Protocol):
    """Public interface of the client, used by server.py."""

    def search_contracts(self, search: str) -> list[dict]:
        """Text search (the API also matches number, description and file)."""

    def list_contracts(self) -> list[dict]:
        """All visible contracts (the endpoint has no pagination)."""

    def get_contract_detail(self, contract_id: str) -> dict:
        """Detail of a single contract."""

    def get_contract_clauses(self, contract_id: str) -> list[dict]:
        """Clauses of a contract."""


# ---------------------------------------------------------------------------
# Mapping of the API records (camelCase) to the tool fields
# ---------------------------------------------------------------------------


def contract_for_tool(record: dict) -> dict:
    """Maps an API record to the fields returned by the search tool."""
    return {
        "id": record["id"],
        "number": record["contractNumber"],
        "supplier_name": record["supplierName"],
        "status": record["status"],
    }


def detail_for_tool(record: dict) -> dict:
    """Maps the API detail to the fields returned by the detail tool."""
    detail = contract_for_tool(record)
    detail.update(
        {
            "supplier_id": record.get("supplierId"),
            "description": record.get("description"),
            "start_date": record.get("startDate"),
            "end_date": record.get("endDate"),
        }
    )
    return detail


# ---------------------------------------------------------------------------
# Local simulation
# ---------------------------------------------------------------------------


class SimulatedContractsApi:
    """Deterministic simulation of the API with synthetic data.

    The records mirror the examples in docs/contracts-api.md.
    ``supplier_id`` (optional) simulates an external supplier user,
    who can only see their own contracts: this is the "denied access"
    case requested by the documentation for local testing.
    """

    # Contracts of the "demo" tenant (visible).
    _TENANT_DEMO = [
        {
            "id": "demo-001",
            "contractNumber": "A-2026-001",
            "supplierId": "supplier-alfa",
            "supplierName": "Alfa S.p.A.",
            "status": "VALID",
            "description": "Maintenance",
            "startDate": "2026-01-01",
            "endDate": "2026-12-31",
        },
        {
            "id": "demo-002",
            "contractNumber": "A-2026-002",
            "supplierId": "supplier-alfa",
            "supplierName": "Alfa S.p.A.",
            "status": "NEGOTIATION",
            "description": "Materials",
            "startDate": None,
            "endDate": None,
        },
        {
            "id": "demo-003",
            "contractNumber": "A-2026-003",
            "supplierId": "supplier-beta",
            "supplierName": "Beta S.r.l.",
            "status": "DRAFT",
            "description": "Setup",
            "startDate": "2026-03-01",
            "endDate": "2026-12-31",
        },
        # The description contains "alfa" but the supplier is Beta:
        # it serves to verify that the tool filters by supplier name.
        {
            "id": "demo-004",
            "contractNumber": "A-2026-004",
            "supplierId": "supplier-beta",
            "supplierName": "Beta S.r.l.",
            "status": "PROCESSING",
            "description": "Spare parts for Alfa",
            "startDate": None,
            "endDate": None,
        },
    ]

    # Contracts used to simulate the error cases requested
    # by the documentation: they are visible in search and in the list,
    # but the detail (and the clauses) fails as indicated by the id.
    _SPECIAL_CONTRACTS = [
        # Denied access: the current identity does not have
        # read permission on this contract.
        {
            "id": "denied-001",
            "contractNumber": "A-2026-101",
            "supplierId": "supplier-delta",
            "supplierName": "Delta S.p.A.",
            "status": "CLOSE_TO_EXPIRATION",
            "description": "Assistance",
            "startDate": "2025-01-01",
            "endDate": "2026-06-30",
        },
        # Internal API error (HTTP 500).
        {
            "id": "error-001",
            "contractNumber": "A-2026-102",
            "supplierId": "supplier-delta",
            "supplierName": "Delta S.p.A.",
            "status": "VALID",
            "description": "Maintenance",
            "startDate": "2026-01-01",
            "endDate": "2026-12-31",
        },
        # Call timeout: the response does not arrive in time.
        {
            "id": "timeout-001",
            "contractNumber": "A-2026-103",
            "supplierId": "supplier-delta",
            "supplierName": "Delta S.p.A.",
            "status": "DRAFT",
            "description": "Consulting",
            "startDate": None,
            "endDate": None,
        },
    ]

    # Contract of another synthetic tenant: never visible (separation).
    _OTHER_TENANT = [
        {
            "id": "other-001",
            "contractNumber": "X-2026-001",
            "supplierId": "supplier-gamma",
            "supplierName": "Gamma S.p.A.",
            "status": "VALID",
            "description": "Off-grid",
            "startDate": "2026-02-01",
            "endDate": "2026-11-30",
        },
    ]

    _CLAUSES = {
        "demo-001": [
            {
                "id": 1,
                "clauseCode": "PAYMENT",
                "clauseType": "commercial",
                "description": "Payment within 30 days",
            }
        ],
        "demo-002": [
            {
                "id": 2,
                "clauseCode": "TERM",
                "clauseType": "commercial",
                "description": "Auto-renewal every 3 years",
            }
        ],
    }

    def __init__(self, supplier_id: str | None = None) -> None:
        # None = full visibility of the "demo" tenant;
        # otherwise only the contracts of the given supplier.
        self._supplier_id = supplier_id

    def _all_contracts(self) -> list[dict]:
        """All contracts of the "demo" tenant, including the special ones."""
        return self._TENANT_DEMO + self._SPECIAL_CONTRACTS

    def _visible_contracts(self) -> list[dict]:
        visible = [dict(c) for c in self._all_contracts()]
        if self._supplier_id is not None:
            visible = [c for c in visible if c["supplierId"] == self._supplier_id]
        return visible

    def search_contracts(self, search: str) -> list[dict]:
        # Like the real API, the partial search (case-insensitive)
        # also matches number and description.
        text = search.lower()
        return [
            c
            for c in self._visible_contracts()
            if text in c["supplierName"].lower()
            or text in c["contractNumber"].lower()
            or text in (c.get("description") or "").lower()
        ]

    def list_contracts(self) -> list[dict]:
        return self._visible_contracts()

    def get_contract_detail(self, contract_id: str) -> dict:
        for contract in self._all_contracts():
            if contract["id"] != contract_id:
                continue
            if (
                self._supplier_id is not None
                and contract["supplierId"] != self._supplier_id
            ):
                raise ApiError(
                    403, "the contract belongs to another supplier"
                )
            # Simulated error cases (see the class docstring).
            if contract_id == "denied-001":
                raise ApiError(
                    403,
                    "the current identity does not have read permission "
                    "on this contract",
                )
            if contract_id == "error-001":
                raise ApiError(500, "Internal server error (simulated)")
            if contract_id == "timeout-001":
                raise ApiError(0, "the request did not return in time (simulated)")
            return dict(contract)
        # Unknown id, or contract of another tenant (not visible).
        raise ApiError(404, f"No contract with id {contract_id}")

    def get_contract_clauses(self, contract_id: str) -> list[dict]:
        # The clauses follow the same access rules as the detail.
        self.get_contract_detail(contract_id)
        return [dict(c) for c in self._CLAUSES.get(contract_id, [])]


# ---------------------------------------------------------------------------
# Real API
# ---------------------------------------------------------------------------


class HttpContractsApi:
    """Client for the real Evolution API (read-only operations)."""

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        timeout: float = TIMEOUT_DEFAULT,
    ) -> None:
        headers = {}
        # No invented tenant headers: the bearer token is only used
        # if explicitly configured through EVOLUTION_API_TOKEN.
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout
        )

    def _get(self, path: str, params: dict | None = None):
        try:
            response = self._client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise ApiError(0, f"Network error contacting the API: {exc}") from exc
        if response.status_code >= 400:
            raise ApiError(response.status_code, self._error_message(response))
        return response.json()

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            for key in ("message", "detail", "error"):
                if key in body:
                    return str(body[key])
        if body is not None:
            return str(body)
        return response.text[:200] or f"HTTP {response.status_code}"

    def search_contracts(self, search: str) -> list[dict]:
        return self._get("/api/contracts", params={"search": search})

    def list_contracts(self) -> list[dict]:
        return self._get("/api/contracts")

    def get_contract_detail(self, contract_id: str) -> dict:
        return self._get(f"/api/contracts/{quote(contract_id, safe='')}")

    def get_contract_clauses(self, contract_id: str) -> list[dict]:
        return self._get(f"/api/contracts/{quote(contract_id, safe='')}/clauses")


# ---------------------------------------------------------------------------
# Client selection
# ---------------------------------------------------------------------------


def create_client() -> ContractsApi:
    """Returns the active client based on the environment.

    If ``EVOLUTION_API_BASE_URL`` is set, uses the real API;
    otherwise uses the local simulation.
    """
    base_url = os.environ.get(ENV_BASE_URL, "").strip()
    if base_url:
        token = os.environ.get(ENV_TOKEN, "").strip() or None
        return HttpContractsApi(base_url, token=token)
    supplier_id = os.environ.get(ENV_SIMULATION_SUPPLIER, "").strip() or None
    return SimulatedContractsApi(supplier_id=supplier_id)
