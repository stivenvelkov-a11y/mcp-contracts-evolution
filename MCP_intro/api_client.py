"""Client read-only per l'Evolution Contracts API.

Implementa gli endpoint descritti in docs/contracts-api.md:

- ``GET /api/contracts?search=<testo>``          (ricerca)
- ``GET /api/contracts?supplierId=<id>``         (filtro per id fornitore)
- ``GET /api/contracts?status=<stato>``          (filtro per stato)
- ``GET /api/contracts/{contractId}``            (dettaglio)
- ``GET /api/contracts/{contractId}/clauses``    (clausole, opzionale)

Due backend intercambiabili, scelti in base all'ambiente, così lo
stesso server può passare alla API reale senza cambiare
l'interfaccia pubblica dei tool (vedi README):

- ``HttpContractsApi``: chiamate HTTP alla API reale, usata quando
  è impostata ``EVOLUTION_API_BASE_URL`` (l'URL e il flusso token
  saranno forniti dal team dopo la revisione dell'integrazione
  locale; non si inventano header di tenant).
- ``SimulatedContractsApi``: simulazione locale deterministica con
  dati sintetichi che rispecchiano gli esempi della documentazione e
  copre i casi richiesti per la prova locale: risultati, ricerca
  vuota, id sconosciuto, accesso negato, errore interno dell'API,
  timeout e separazione tra tenant sintetici. Per provare i casi di
  errore si usa ``get_contract`` con questi id dedicati (visibili
  anche in ricerca sotto il fornitore "Delta S.p.A."):

  - ``denied-001``  -> accesso negato (HTTP 403);
  - ``errore-001``  -> errore interno dell'API (HTTP 500);
  - ``timeout-001`` -> timeout della chiamata (nessuna risposta in tempo).

Variabili d'ambiente (tutte opzionali):
- ``EVOLUTION_API_BASE_URL``: URL base della API reale (es. https://ambiente.evolution).
- ``EVOLUTION_API_TOKEN``: bearer token, solo se esplicitamente
  configurato (il flusso sarà confermato con il team).
- ``EVOLUTION_SIMULATION_SUPPLIER_ID``: nella simulazione, restringe
  la visibilità al fornitore indicato (utente esterno).
"""

from __future__ import annotations

import os
from typing import Protocol
from urllib.parse import quote

import httpx

# Variabili d'ambiente
ENV_BASE_URL = "EVOLUTION_API_BASE_URL"
ENV_TOKEN = "EVOLUTION_API_TOKEN"
ENV_SIMULATION_SUPPLIER = "EVOLUTION_SIMULATION_SUPPLIER_ID"

# Timeout in secondi per le chiamate HTTP
TIMEOUT_DEFAULT = 10.0


class ApiError(Exception):
    """Errore restituito dalla API (simulata o reale)."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message


class ContractsApi(Protocol):
    """Interfaccia pubblica del client, usata da server.py."""

    def cerca_contratti(self, search: str) -> list[dict]:
        """Ricerca per testo (l'API confronta anche numero, descrizione e file)."""

    def elenco_contratti(self) -> list[dict]:
        """Tutti i contratti visibili (l'endpoint non ha paginazione)."""

    def dettaglio_contratto(self, contract_id: str) -> dict:
        """Dettaglio di un singolo contratto."""

    def clausole_contratto(self, contract_id: str) -> list[dict]:
        """Clausole di un contratto."""


# ---------------------------------------------------------------------------
# Mappatura dei record API (camelCase) sui campi dei tool
# ---------------------------------------------------------------------------


def contratto_per_tool(record: dict) -> dict:
    """Mappa un record API sui campi restituiti dal tool di ricerca."""
    return {
        "id": record["id"],
        "numero": record["contractNumber"],
        "nome_fornitore": record["supplierName"],
        "stato": record["status"],
    }


def dettaglio_per_tool(record: dict) -> dict:
    """Mappa il dettaglio API sui campi restituiti dal tool di dettaglio."""
    dettaglio = contratto_per_tool(record)
    dettaglio.update(
        {
            "id_fornitore": record.get("supplierId"),
            "descrizione": record.get("description"),
            "data_inizio": record.get("startDate"),
            "data_fine": record.get("endDate"),
        }
    )
    return dettaglio


# ---------------------------------------------------------------------------
# Simulazione locale
# ---------------------------------------------------------------------------


class SimulatedContractsApi:
    """Simulazione deterministica della API con dati sintetichi.

    I record rispecchiano gli esempi di docs/contracts-api.md.
    ``supplier_id`` (opzionale) simula un utente esterno fornitore,
    che vede solo i propri contratti: è il caso "accesso negato"
    richiesto dalla documentazione per la prova locale.
    """

    # Contratti del tenant "demo" (visibili).
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
        # La descrizione contiene "alfa" ma il fornitore è Beta:
        # serve a verificare che il tool filtri per nome fornitore.
        {
            "id": "demo-004",
            "contractNumber": "A-2026-004",
            "supplierId": "supplier-beta",
            "supplierName": "Beta S.r.l.",
            "status": "PROCESSING",
            "description": "Ricambi per Alfa",
            "startDate": None,
            "endDate": None,
        },
    ]

    # Contratti che servono a simulare i casi di errore richiesti
    # dalla documentazione: sono visibili in ricerca e nell'elenco,
    # ma il dettaglio (e le clausole) fallisce come indicato dall'id.
    _CONTRATTI_SPECIALI = [
        # Accesso negato: l'identità corrente non ha il permesso di
        # lettura su questo contratto.
        {
            "id": "denied-001",
            "contractNumber": "A-2026-101",
            "supplierId": "supplier-delta",
            "supplierName": "Delta S.p.A.",
            "status": "CLOSE_TO_EXPIRATION",
            "description": "Assistenza",
            "startDate": "2025-01-01",
            "endDate": "2026-06-30",
        },
        # Errore interno dell'API (HTTP 500).
        {
            "id": "errore-001",
            "contractNumber": "A-2026-102",
            "supplierId": "supplier-delta",
            "supplierName": "Delta S.p.A.",
            "status": "VALID",
            "description": "Manutenzione",
            "startDate": "2026-01-01",
            "endDate": "2026-12-31",
        },
        # Timeout della chiamata: la risposta non arriva in tempo.
        {
            "id": "timeout-001",
            "contractNumber": "A-2026-103",
            "supplierId": "supplier-delta",
            "supplierName": "Delta S.p.A.",
            "status": "DRAFT",
            "description": "Consulenza",
            "startDate": None,
            "endDate": None,
        },
    ]

    # Contratto di un altro tenant sintetico: mai visibile (separazione).
    _ALTRO_TENANT = [
        {
            "id": "altro-001",
            "contractNumber": "X-2026-001",
            "supplierId": "supplier-gamma",
            "supplierName": "Gamma S.p.A.",
            "status": "VALID",
            "description": "Off-grid",
            "startDate": "2026-02-01",
            "endDate": "2026-11-30",
        },
    ]

    _CLAUSOLE = {
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
        # None = visibilità completa del tenant "demo";
        # altrimenti solo i contratti del fornitore indicato.
        self._supplier_id = supplier_id

    def _tutti(self) -> list[dict]:
        """Tutti i contratti del tenant "demo", compresi quelli speciali."""
        return self._TENANT_DEMO + self._CONTRATTI_SPECIALI

    def _visibili(self) -> list[dict]:
        visibili = [dict(c) for c in self._tutti()]
        if self._supplier_id is not None:
            visibili = [c for c in visibili if c["supplierId"] == self._supplier_id]
        return visibili

    def cerca_contratti(self, search: str) -> list[dict]:
        # Come l'API reale, la ricerca parziale (senza distinzione
        # maiuscole/minuscole) confronta anche numero e descrizione.
        testo = search.lower()
        return [
            c
            for c in self._visibili()
            if testo in c["supplierName"].lower()
            or testo in c["contractNumber"].lower()
            or testo in (c.get("description") or "").lower()
        ]

    def elenco_contratti(self) -> list[dict]:
        return self._visibili()

    def dettaglio_contratto(self, contract_id: str) -> dict:
        for contratto in self._tutti():
            if contratto["id"] != contract_id:
                continue
            if (
                self._supplier_id is not None
                and contratto["supplierId"] != self._supplier_id
            ):
                raise ApiError(
                    403, "il contratto appartiene a un altro fornitore"
                )
            # Casi di errore simulati (vedi il docstring della classe).
            if contract_id == "denied-001":
                raise ApiError(
                    403,
                    "l'identità corrente non ha il permesso di lettura "
                    "su questo contratto",
                )
            if contract_id == "errore-001":
                raise ApiError(500, "Errore interno del server (simulato)")
            if contract_id == "timeout-001":
                raise ApiError(0, "la richiesta non è tornata in tempo (simulato)")
            return dict(contratto)
        # Id sconosciuto, o contratto di un altro tenant (non visibile).
        raise ApiError(404, f"Nessun contratto con id {contract_id}")

    def clausole_contratto(self, contract_id: str) -> list[dict]:
        # Le clausole seguono le stesse regole di accesso del dettaglio.
        self.dettaglio_contratto(contract_id)
        return [dict(c) for c in self._CLAUSOLE.get(contract_id, [])]


# ---------------------------------------------------------------------------
# API reale
# ---------------------------------------------------------------------------


class HttpContractsApi:
    """Client per la API Evolution reale (solo operazioni di lettura)."""

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        timeout: float = TIMEOUT_DEFAULT,
    ) -> None:
        headers = {}
        # Nessun header di tenant inventato: il bearer si usa solo se
        # esplicitamente configurato tramite EVOLUTION_API_TOKEN.
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout
        )

    def _get(self, path: str, params: dict | None = None):
        try:
            response = self._client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise ApiError(0, f"Errore di rete verso la API: {exc}") from exc
        if response.status_code >= 400:
            raise ApiError(response.status_code, self._messaggio_errore(response))
        return response.json()

    @staticmethod
    def _messaggio_errore(response: httpx.Response) -> str:
        try:
            corpo = response.json()
        except ValueError:
            corpo = None
        if isinstance(corpo, dict):
            for chiave in ("message", "detail", "error"):
                if chiave in corpo:
                    return str(corpo[chiave])
        if corpo is not None:
            return str(corpo)
        return response.text[:200] or f"HTTP {response.status_code}"

    def cerca_contratti(self, search: str) -> list[dict]:
        return self._get("/api/contracts", params={"search": search})

    def elenco_contratti(self) -> list[dict]:
        return self._get("/api/contracts")

    def dettaglio_contratto(self, contract_id: str) -> dict:
        return self._get(f"/api/contracts/{quote(contract_id, safe='')}")

    def clausole_contratto(self, contract_id: str) -> list[dict]:
        return self._get(f"/api/contracts/{quote(contract_id, safe='')}/clauses")


# ---------------------------------------------------------------------------
# Scelta del client
# ---------------------------------------------------------------------------


def crea_client() -> ContractsApi:
    """Restituisce il client attivo in base all'ambiente.

    Se ``EVOLUTION_API_BASE_URL`` è impostata usa la API reale,
    altrimenti la simulazione locale.
    """
    base_url = os.environ.get(ENV_BASE_URL, "").strip()
    if base_url:
        token = os.environ.get(ENV_TOKEN, "").strip() or None
        return HttpContractsApi(base_url, token=token)
    supplier_id = os.environ.get(ENV_SIMULATION_SUPPLIER, "").strip() or None
    return SimulatedContractsApi(supplier_id=supplier_id)
