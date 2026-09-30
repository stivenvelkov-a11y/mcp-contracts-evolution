"""Opens and reads the data/contracts.db database.

Prints all contracts in table form, followed by a
summary by status and by type.
"""

from collections import Counter
from pathlib import Path
import sqlite3

# Database path: the "data" folder at the project root
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "contracts.db"

COLUMNS = ("id", "number", "supplier_name", "status", "contract_type")


def read_contracts(db_path: Path = DB_PATH) -> list[tuple]:
    """Returns all contracts as a list of tuples ordered by id."""
    con = sqlite3.connect(db_path)
    try:
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT id, number, supplier_name, status, contract_type FROM contracts ORDER BY id"
        )
        return [tuple(row) for row in cur.fetchall()]
    finally:
        con.close()


def print_table(contracts: list[tuple]) -> None:
    """Prints the contracts in an aligned table form."""
    rows = [COLUMNS] + [tuple(str(val) for val in contract) for contract in contracts]
    widths = [max(len(r[i]) for r in rows) for i in range(len(COLUMNS))]

    def format_row(row):
        return "  ".join(val.ljust(l) for val, l in zip(row, widths))

    print(format_row(COLUMNS))
    print("-" * (sum(widths) + 2 * len(widths)))
    for row in rows[1:]:
        print(format_row(row))


def summary(contracts: list[tuple]) -> None:
    """Prints counts by status and by type."""
    by_status = Counter(c[3] for c in contracts)
    by_type = Counter(c[4] for c in contracts)
    print(f"\nTotal contracts: {len(contracts)}")
    print("By status: " + ", ".join(f"{k}={v}" for k, v in by_status.items()))
    print("By type:  " + ", ".join(f"{k}={v}" for k, v in by_type.items()))


def main() -> None:
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        print("Run the generator first: python dataset/generate_db.py")
        return

    contracts = read_contracts()
    if not contracts:
        print("No contracts found in the database.")
        return

    print_table(contracts)
    summary(contracts)


if __name__ == "__main__":
    main()
