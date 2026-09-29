"""Genera il database SQLite data/contratti.db.

Crea (o ricrea) la tabella `contratti` e la popola con i dati di
esempio, in modo che il dataset sia sempre riproducibile.
"""

from pathlib import Path
import sqlite3

# Percorso del database: cartella "data" alla radice del progetto
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "contratti.db"

# Dati di esempio da caricare nella tabella
CONTRATTI = [
    ("CT-2026-001", "ALFA", "attivo", "annuale"),
    ("CT-2026-002", "ALFA", "inattivo", "quinquennale"),
    ("CT-2026-003", "Beta", "attivo", "biennale"),
]


def genera_db(db_path: Path = DB_PATH) -> None:
    """Crea il database e la tabella contratti con i dati di esempio."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        # Ricrea la tabella da zero: il dataset è sempre riproducibile
        cur.execute("DROP TABLE IF EXISTS contratti")
        cur.execute(
            """
            CREATE TABLE contratti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT NOT NULL UNIQUE,
                nome_fornitore TEXT NOT NULL,
                stato TEXT NOT NULL CHECK (stato IN ('attivo', 'inattivo')),
                tipo TEXT NOT NULL CHECK (tipo IN ('annuale', 'biennale', 'quinquennale'))
            )
            """
        )
        cur.executemany(
            "INSERT INTO contratti (numero, nome_fornitore, stato, tipo) VALUES (?, ?, ?, ?)",
            CONTRATTI,
        )
        con.commit()
    finally:
        con.close()

    print(f"Database generato: {DB_PATH}")


if __name__ == "__main__":
    genera_db()
