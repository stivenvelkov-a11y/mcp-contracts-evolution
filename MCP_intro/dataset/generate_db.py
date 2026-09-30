"""Generates the data/contracts.db SQLite database.

Creates (or recreates) the `contracts` table and populates it with
sample data, so that the dataset is always reproducible.
"""

from pathlib import Path
import sqlite3

# Database path: the "data" folder at the project root
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "contracts.db"

# Sample data to load into the table
CONTRACTS = [
    ("CT-2026-001", "ALFA", "active", "annual"),
    ("CT-2026-002", "ALFA", "inactive", "quinquennial"),
    ("CT-2026-003", "Beta", "active", "biennial"),
]


def generate_db(db_path: Path = DB_PATH) -> None:
    """Creates the database and the contracts table with the sample data."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        # Recreates the table from scratch: the dataset is always reproducible
        cur.execute("DROP TABLE IF EXISTS contracts")
        cur.execute(
            """
            CREATE TABLE contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number TEXT NOT NULL UNIQUE,
                supplier_name TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('active', 'inactive')),
                contract_type TEXT NOT NULL CHECK (contract_type IN ('annual', 'biennial', 'quinquennial'))
            )
            """
        )
        cur.executemany(
            "INSERT INTO contracts (number, supplier_name, status, contract_type) VALUES (?, ?, ?, ?)",
            CONTRACTS,
        )
        con.commit()
    finally:
        con.close()

    print(f"Database generated: {DB_PATH}")


if __name__ == "__main__":
    generate_db()
