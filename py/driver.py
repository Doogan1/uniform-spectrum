# py/driver.py
"""Batch-checks the uniform spectrum conjecture across all graphs of one order."""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# When run directly as `python py/driver.py`, Python puts py/'s own directory
# on sys.path, not the repo root -- so `from py import ...` below would fail
# with ModuleNotFoundError unless the repo root is added explicitly here.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "core" / "build"))
import uniform_spectrum_core as core  # noqa: E402

from py import conjecture, generate  # noqa: E402

DEFAULT_CHECKPOINT_INTERVAL = 1000


def init_db(conn: sqlite3.Connection, n: int) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY CHECK (id = 0),
            n INTEGER NOT NULL,
            last_index INTEGER NOT NULL,
            status TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS violations (
            graph6 TEXT NOT NULL,
            spectrum TEXT NOT NULL,
            found_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS summary (
            id INTEGER PRIMARY KEY CHECK (id = 0),
            graphs_checked INTEGER NOT NULL,
            n_minus_1_in_spectrum INTEGER NOT NULL,
            conjecture_holds INTEGER NOT NULL,
            conjecture_violations INTEGER NOT NULL,
            not_applicable INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO progress (id, n, last_index, status) VALUES (0, ?, -1, 'running')",
        (n,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO summary "
        "(id, graphs_checked, n_minus_1_in_spectrum, conjecture_holds, conjecture_violations, not_applicable) "
        "VALUES (0, 0, 0, 0, 0, 0)"
    )
    conn.commit()


def get_progress(conn: sqlite3.Connection) -> tuple:
    row = conn.execute("SELECT last_index, status FROM progress WHERE id = 0").fetchone()
    return row[0], row[1]


def record_result(
    conn: sqlite3.Connection,
    index: int,
    graph6: str,
    spectrum: set,
    n_minus_1_in_spectrum: bool,
    holds,
) -> None:
    conn.execute("UPDATE progress SET last_index = ? WHERE id = 0", (index,))
    conn.execute(
        "UPDATE summary SET "
        "graphs_checked = graphs_checked + 1, "
        "n_minus_1_in_spectrum = n_minus_1_in_spectrum + ?, "
        "conjecture_holds = conjecture_holds + ?, "
        "conjecture_violations = conjecture_violations + ?, "
        "not_applicable = not_applicable + ? "
        "WHERE id = 0",
        (
            int(n_minus_1_in_spectrum),
            int(holds is True),
            int(holds is False),
            int(holds is None),
        ),
    )
    if holds is False:
        conn.execute(
            "INSERT INTO violations (graph6, spectrum, found_at) VALUES (?, ?, ?)",
            (graph6, json.dumps(sorted(spectrum)), datetime.now(timezone.utc).isoformat()),
        )


def mark_complete(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE progress SET status = 'complete' WHERE id = 0")


def run(n: int, db_path, checkpoint_interval: int = DEFAULT_CHECKPOINT_INTERVAL) -> None:
    conn = sqlite3.connect(db_path)
    try:
        init_db(conn, n)
        stored_n = conn.execute("SELECT n FROM progress WHERE id = 0").fetchone()[0]
        if stored_n != n:
            raise ValueError(
                f"Database {db_path} was created for order {stored_n}, "
                f"but run() was called with order {n}. Refusing to mix results "
                f"from different orders in the same database."
            )
        last_index, status = get_progress(conn)
        if status == "complete":
            return
        for index, graph6 in enumerate(generate.run_geng(n)):
            if index <= last_index:
                continue
            spectrum = core.spectrum_from_graph6(graph6)
            holds = conjecture.check(n, spectrum)
            n_minus_1_in_spectrum = (n - 1) in spectrum
            record_result(conn, index, graph6, spectrum, n_minus_1_in_spectrum, holds)
            if (index + 1) % checkpoint_interval == 0:
                conn.commit()
        mark_complete(conn)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Exhaustively check the uniform spectrum conjecture for all graphs of a given order."
    )
    parser.add_argument("n", type=int, help="graph order to check")
    parser.add_argument(
        "--db", type=str, default=None, help="path to results sqlite db (default: results/order_<n>.sqlite)"
    )
    args = parser.parse_args()
    db_path = args.db or f"results/order_{args.n}.sqlite"
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    run(args.n, db_path)
    print(f"Done. Results in {db_path}")
