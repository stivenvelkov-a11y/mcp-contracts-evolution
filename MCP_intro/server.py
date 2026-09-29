"""MCP server read-only per l'Evolution Contracts API.

Espone due strumenti:
- search_contract: cerca i contratti di un fornitore per nome e
  restituisce i contratti trovati con id, numero, nome_fornitore e stato.
- get_contract: restituisce il dettaglio completo di un contratto, dato il suo id.

Le chiamate alla API sono centralizzate in api_client.py, che
implementa gli endpoint di docs/contracts-api.md. Se non è impostata
EVOLUTION_API_BASE_URL viene usata una simulazione locale con dati
sintetici (vedi il modulo api_client per i dettagli).

Avvio (trasporto stdio):
    python server.py

Esempio di configurazione lato client (Claude Desktop, OpenCode, ecc.):
    {
        "mcpServers": {
            "contratti": {
                "command": "python",
                "args": ["C:/percorso/a/MCP_intro/server.py"]
            }
        }
    }
"""

from mcp.server.mcpserver import MCPServer

from api_client import ApiError, contratto_per_tool, crea_client, dettaglio_per_tool

mcp = MCPServer("contratti")

# Client API attivo (reale o simulazione, scelto da api_client.crea_client)
client = crea_client()


def _errore_api(exc: ApiError, operazione: str) -> dict:
    """Trasforma un errore API (diverso dal 404) in un dizionario leggibile.

    Il 404 viene gestito dai singoli tool con un messaggio più
    specifico (es. "Nessun contratto con id ...").
    """
    if exc.status == 403:
        dettaglio = "Accesso negato"
    elif exc.status == 0:
        dettaglio = "Timeout o errore di rete"
    else:
        dettaglio = f"Errore dell'API (HTTP {exc.status})"
    return {"errore": f"{dettaglio} durante {operazione}: {exc.message}"}


@mcp.tool()
def search_contract(nome_fornitore: str) -> dict | list[dict]:
    """Cerca i contratti di un fornitore per nome (cerca parziale, senza distinzione maiuscole/minuscole).

    Restituisce l'elenco dei contratti trovati con id, numero,
    nome_fornitore e stato. Se nessuna riga corrisponde, l'elenco è vuoto.
    Se nome_fornitore è vuoto (o contiene solo spazi), non esegue la
    ricerca e restituisce un dizionario con la chiave "errore".
    """
    nome = nome_fornitore.strip()
    if not nome:
        return {"errore": "nome_fornitore non può essere vuoto"}
    try:
        risultati = client.cerca_contratti(nome)
    except ApiError as exc:
        return _errore_api(exc, "la ricerca")
    # La `search` della API confronta anche numero, descrizione e file:
    # per mantenere la promessa del tool (solo per nome fornitore)
    # si conservano i contratti il cui nome fornitore corrisponde
    # (vedi docs/contracts-api.md).
    return [
        contratto_per_tool(c)
        for c in risultati
        if nome.lower() in c["supplierName"].lower()
    ]


@mcp.tool()
def get_contract(id: str) -> dict:
    """Restituisce il dettaglio completo di un contratto, dato il suo id.

    Se nessun contratto ha quell'id, restituisce un dizionario
    con la chiave "errore".
    """
    contract_id = id.strip()
    if not contract_id:
        return {"errore": "id non può essere vuoto"}
    try:
        record = client.dettaglio_contratto(contract_id)
    except ApiError as exc:
        if exc.status == 404:
            return {"errore": f"Nessun contratto con id {id}"}
        return _errore_api(exc, "il recupero del dettaglio")
    return dettaglio_per_tool(record)


if __name__ == "__main__":
    mcp.run()
