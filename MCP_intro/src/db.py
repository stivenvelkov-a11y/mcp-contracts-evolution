"""Apre e legge il database data/contratti.db.

Stampa tutti i contratti in formato tabellare, seguiti da un
riepilogo per stato e per tipo.
"""

from collections import Counter
from pathlib import Path
import sqlite3

# Percorso del database: cartella "data" alla radice del progetto
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "contratti.db"

COLONNE = ("id", "numero", "nome_fornitore", "stato", "tipo")


def leggi_contratti(db_path: Path = DB_PATH) -> list[tuple]:
    """Restituisce tutti i contratti come lista di tuple ordinate per id."""
    con = sqlite3.connect(db_path)
    try:
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT id, numero, nome_fornitore, stato, tipo FROM contratti ORDER BY id"
        )
        return [tuple(row) for row in cur.fetchall()]
    finally:
        con.close()


def stampa_tabella(contratti: list[tuple]) -> None:
    """Stampa i contratti in forma tabellare allineata."""
    righe = [COLONNE] + [tuple(str(val) for val in contratto) for contratto in contratti]
    larghezze = [max(len(r[i]) for r in righe) for i in range(len(COLONNE))]

    def formatta(riga):
        return "  ".join(val.ljust(l) for val, l in zip(riga, larghezze))

    print(formatta(COLONNE))
    print("-" * (sum(larghezze) + 2 * len(larghezze)))
    for riga in righe[1:]:
        print(formatta(riga))


def riepilogo(contratti: list[tuple]) -> None:
    """Stampa conteggi per stato e per tipo."""
    per_stato = Counter(c[3] for c in contratti)
    per_tipo = Counter(c[4] for c in contratti)
    print(f"\nTotale contratti: {len(contratti)}")
    print("Per stato: " + ", ".join(f"{k}={v}" for k, v in per_stato.items()))
    print("Per tipo:  " + ", ".join(f"{k}={v}" for k, v in per_tipo.items()))


def main() -> None:
    if not DB_PATH.exists():
        print(f"Database non trovato: {DB_PATH}")
        print("Esegui prima il generatore: python dataset/genera_db.py")
        return

    contratti = leggi_contratti()
    if not contratti:
        print("Nessun contratto trovato nel database.")
        return

    stampa_tabella(contratti)
    riepilogo(contratti)


if __name__ == "__main__":
    main()
