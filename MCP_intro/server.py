"""MCP server per il database data/contratti.db.

Espone due strumenti:
- search_contract: cerca i contratti di un fornitore per nome e
  restituisce i contratti trovati con id, numero, nome_fornitore e stato.
- get_contract: restituisce il dettaglio completo di un contratto, dato il suo id.

Avvio (trasporto stdio):
    python server.py

Esempio di configurazione lato client (Claude Desktop, OpenCode, ecc.):
    {
        "mcpServers": {
            "contratti": {
                "command": "python",
                "args": ["C:/Users/u1901/Documents/MCP_intro/server.py"]
            }
        }
    }
"""

from pathlib import Path
import sqlite3

from mcp.server.mcpserver import MCPServer

# Percorso del database: cartella "data" alla radice del progetto
DB_PATH = Path(__file__).resolve().parent / "data" / "contratti.db"

mcp = MCPServer("contratti")


def _connessione() -> sqlite3.Connection:
    """Apre una connessione al database con righe in stile dizionario."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


@mcp.tool()
def search_contract(nome_fornitore: str) -> list[dict]:
    """Cerca i contratti di un fornitore per nome (cerca parziale, senza distinzione maiuscole/minuscole).

    Restituisce l'elenco dei contratti trovati con id, numero,
    nome_fornitore e stato. Se nessuna riga corrisponde, l'elenco è vuoto.
    """
    nome = nome_fornitore.strip()
    con = _connessione()
    try:
        cur = con.execute(
            "SELECT id, numero, nome_fornitore, stato FROM contratti "
            "WHERE nome_fornitore LIKE ? ORDER BY id",
            (f"%{nome}%",),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        con.close()


@mcp.tool()
def get_contract(id: int) -> dict:
    """Restituisce il dettaglio completo di un contratto, dato il suo id.

    Se nessun contratto ha quell'id, restituisce un dizionario
    con la chiave "errore".
    """
    con = _connessione()
    try:
        row = con.execute(
            "SELECT id, numero, nome_fornitore, stato, tipo FROM contratti WHERE id = ?",
            (id,),
        ).fetchone()
    finally:
        con.close()

    if row is None:
        return {"errore": f"Nessun contratto con id {id}"}
    return dict(row)


if __name__ == "__main__":
    mcp.run()
