"""Test automatici del server MCP in server.py.

Ogni test avvia il server reale (``python server.py``) come
subprocesso e lo interroga su stdio con un client MCP: la stessa
interazione che esegue l'ispettore MCP, ma scriptata e ripetibile.

Il server usa il client in api_client.py; i test presuppongono la
simulazione locale con dati sintetichi (nessuna EVOLUTION_API_BASE_URL).

Controlli coperti:
- ``search_contract`` restituisce i risultati con una ricerca che
  corrisponde a fornitori noti (anche senza distinzione
  maiuscole/minuscole) e solo i contratti del fornitore cercato;
- ``search_contract`` restituisce un elenco vuoto con una ricerca
  senza corrispondenze;
- ``get_contract`` restituisce il dettaglio completo con un id valido;
- ``get_contract`` restituisce un errore con un id inesistente;
- ``get_contract`` restituisce un errore di accesso negato per un
  contratto protetto (id ``denied-001``);
- ``get_contract`` restituisce un errore leggibile se la API fallisce
  con HTTP 500 (id ``errore-001``) o non risponde in tempo, timeout
  (id ``timeout-001``);
- ``search_contract`` non restituisce tutti i contratti quando gli
  viene passato un nome fornitore vuoto (o solo spazi).

Esecuzione (dalla cartella MCP_intro):
    .venv\\Scripts\\python -m pytest tests/ -v
"""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# Radice del progetto: la cartella che contiene server.py
RAV = Path(__file__).resolve().parent.parent
SERVER_PATH = RAV / "server.py"

# Garantisce l'import di api_client anche se pytest non mette la
# radice del progetto nel sys.path.
if str(RAV) not in sys.path:
    sys.path.insert(0, str(RAV))

from api_client import SimulatedContractsApi

TOOL_SEARCH = "search_contract"
TOOL_DETAIL = "get_contract"

# Timeout in secondi per ogni singola richiesta al server
TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _sessione():
    """Avvia il server come subprocesso e apre una sessione di client MCP."""
    parametri = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        cwd=RAV,
    )
    async with stdio_client(parametri) as (lettura, scrittura):
        async with ClientSession(lettura, scrittura) as sessione:
            await sessione.initialize()
            yield sessione


async def _con_sessione(scenario) -> None:
    """Esegue uno scenario asincrono su una singola sessione del server."""
    async with _sessione() as sessione:
        await scenario(sessione)


def _esegui(scenario) -> None:
    """Esegue uno scenario in un nuovo event loop (pytest senza plugin async)."""
    asyncio.run(_con_sessione(scenario))


def _payload(risultato):
    """Estrae il payload restituito dal tool da un CallToolResult."""
    assert not risultato.is_error, (
        f"Il tool ha restituito un errore di protocollo: {risultato.content}"
    )
    if risultato.structured_content is not None:
        contenuto = risultato.structured_content
        # Il server racchiude il payload in un campo "result".
        if isinstance(contenuto, dict) and set(contenuto) == {"result"}:
            return contenuto["result"]
        return contenuto
    # Fallback: il risultato è serializzato come testo JSON.
    assert len(risultato.content) == 1
    testo = json.loads(risultato.content[0].text)
    if isinstance(testo, dict) and set(testo) == {"result"}:
        return testo["result"]
    return testo


def _totale_contratti() -> int:
    """Numero totale di contratti visibili nella simulazione locale."""
    return len(SimulatedContractsApi().elenco_contratti())


# ---------------------------------------------------------------------------
# Scenari
# ---------------------------------------------------------------------------


async def _scenario_tool_esposti(sessione):
    """I due tool sono visibili all'ispettore nella lista dei tool."""
    elenca = await sessione.list_tools()
    nomi = {tool.name for tool in elenca.tools}
    assert {TOOL_SEARCH, TOOL_DETAIL} <= nomi, f"tool mancanti: {nomi}"


async def _scenario_ricerca_con_risultati(sessione):
    ris = _payload(await sessione.call_tool(TOOL_SEARCH, {"nome_fornitore": "ALFA"}))

    assert isinstance(ris, list), f"risultato inatteso: {ris!r}"
    assert len(ris) > 0, "la ricerca di un fornitore noto non ha restituito contratti"
    for contratto in ris:
        assert {"id", "numero", "nome_fornitore", "stato"} <= set(contratto)
        assert "alfa" in contratto["nome_fornitore"].lower()

    # La ricerca è senza distinzione maiuscole/minuscole: anche la
    # query in minuscolo trova "Beta".
    ris_b = _payload(await sessione.call_tool(TOOL_SEARCH, {"nome_fornitore": "beta"}))
    assert isinstance(ris_b, list) and len(ris_b) > 0
    assert all("beta" in c["nome_fornitore"].lower() for c in ris_b)


async def _scenario_ricerca_senza_risultati(sessione):
    ris = _payload(
        await sessione.call_tool(TOOL_SEARCH, {"nome_fornitore": "ZZZ-INESISTENTE"})
    )
    assert isinstance(ris, list), f"risultato inatteso: {ris!r}"
    assert ris == [], "una ricerca senza corrispondenze deve restituire un elenco vuoto"


async def _scenario_dettaglio_id_valido(sessione):
    # Si parte da un id valido ricavato da una ricerca reale.
    trovati = _payload(await sessione.call_tool(TOOL_SEARCH, {"nome_fornitore": "ALFA"}))
    assert isinstance(trovati, list) and len(trovati) > 0
    riferimento = trovati[0]

    dettaglio = _payload(await sessione.call_tool(TOOL_DETAIL, {"id": riferimento["id"]}))
    assert isinstance(dettaglio, dict), f"risultato inatteso: {dettaglio!r}"
    assert "errore" not in dettaglio
    assert dettaglio["id"] == riferimento["id"]
    assert dettaglio["numero"] == riferimento["numero"]
    assert dettaglio["nome_fornitore"] == riferimento["nome_fornitore"]
    assert dettaglio["stato"] == riferimento["stato"]
    # Campoli aggiuntivi del dettaglio API.
    for campo in ("id_fornitore", "descrizione", "data_inizio", "data_fine"):
        assert campo in dettaglio, f"mancante il campo {campo!r} nel dettaglio"


async def _scenario_dettaglio_id_inesistente(sessione):
    dettaglio = _payload(await sessione.call_tool(TOOL_DETAIL, {"id": "inesistente"}))
    assert isinstance(dettaglio, dict), f"risultato inatteso: {dettaglio!r}"
    assert "errore" in dettaglio, "un id inesistente deve restituire un errore"


async def _scenario_accesso_negato(sessione):
    """Il contratto protetto (denied-001) restituisce un errore di accesso negato."""
    dettaglio = _payload(await sessione.call_tool(TOOL_DETAIL, {"id": "denied-001"}))
    assert isinstance(dettaglio, dict), f"risultato inatteso: {dettaglio!r}"
    assert "errore" in dettaglio
    assert "ccesso negato" in dettaglio["errore"], (
        f"il messaggio non segnala l'accesso negato: {dettaglio['errore']!r}"
    )


async def _scenario_errore_api(sessione):
    """Il contratto che simula un errore interno (errore-001) restituisce un errore HTTP 500."""
    dettaglio = _payload(await sessione.call_tool(TOOL_DETAIL, {"id": "errore-001"}))
    assert isinstance(dettaglio, dict), f"risultato inatteso: {dettaglio!r}"
    assert "errore" in dettaglio
    assert "HTTP 500" in dettaglio["errore"], (
        f"il messaggio non segnala l'errore 500: {dettaglio['errore']!r}"
    )


async def _scenario_timeout(sessione):
    """Il contratto che simula un timeout (timeout-001) restituisce un errore di timeout."""
    dettaglio = _payload(await sessione.call_tool(TOOL_DETAIL, {"id": "timeout-001"}))
    assert isinstance(dettaglio, dict), f"risultato inatteso: {dettaglio!r}"
    assert "errore" in dettaglio
    assert "timeout" in dettaglio["errore"].lower(), (
        f"il messaggio non segnala il timeout: {dettaglio['errore']!r}"
    )


async def _scenario_nome_vuoto(sessione):
    """Un nome fornitore vuoto non deve restituire tutti i contratti."""
    totale = _totale_contratti()
    for nome in ("", "   "):
        ris = _payload(await sessione.call_tool(TOOL_SEARCH, {"nome_fornitore": nome}))
        if isinstance(ris, list):
            # Ipotesi accettabile: elenco vuoto. Mai però la tabella intera.
            assert len(ris) < totale, (
                f"il nome {nome!r} ha restituito tutti i "
                f"contratti ({len(ris)} su {totale})"
            )
        else:
            assert isinstance(ris, dict), f"tipo di risultato inatteso: {type(ris)}"
            assert "errore" in ris, (
                f"con il nome {nome!r} il tool non ha restituito un elenco, "
                "ma nemmeno un messaggio di errore"
            )


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_tool_esposti():
    """Gli strumenti search_contract e get_contract sono pubblicati dal server."""
    _esegui(_scenario_tool_esposti)


def test_ricerca_con_risultati():
    """search_contract restituisce i contratti dei fornitori corrispondenti."""
    _esegui(_scenario_ricerca_con_risultati)


def test_ricerca_senza_risultati():
    """search_contract restituisce un elenco vuoto se nessun fornitore corrisponde."""
    _esegui(_scenario_ricerca_senza_risultati)


def test_dettaglio_con_id_valido():
    """get_contract restituisce il dettaglio completo di un contratto esistente."""
    _esegui(_scenario_dettaglio_id_valido)


def test_dettaglio_con_id_inesistente():
    """get_contract restituisce un errore per un id inesistente."""
    _esegui(_scenario_dettaglio_id_inesistente)


def test_accesso_negato():
    """get_contract restituisce un errore di accesso negato per un contratto protetto."""
    _esegui(_scenario_accesso_negato)


def test_errore_api():
    """get_contract restituisce un errore leggibile quando la API fallisce con HTTP 500."""
    _esegui(_scenario_errore_api)


def test_timeout():
    """get_contract restituisce un errore di timeout se la API non risponde in tempo."""
    _esegui(_scenario_timeout)


def test_nome_fornitore_vuoto_non_restituisce_tutti():
    """Con nome fornitore vuoto o solo spazi, search_contract non restituisce tutti i contratti."""
    _esegui(_scenario_nome_vuoto)
