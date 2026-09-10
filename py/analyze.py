"""Prints a human-readable summary of a results database produced by driver.py."""

import sqlite3


def print_summary(db_path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        n, last_index, status = conn.execute(
            "SELECT n, last_index, status FROM progress WHERE id = 0"
        ).fetchone()
        (
            graphs_checked,
            n_minus_1_in_spectrum,
            conjecture_holds,
            conjecture_violations,
            not_applicable,
        ) = conn.execute(
            "SELECT graphs_checked, n_minus_1_in_spectrum, conjecture_holds, "
            "conjecture_violations, not_applicable FROM summary WHERE id = 0"
        ).fetchone()
        violations = conn.execute("SELECT graph6, spectrum FROM violations").fetchall()
    finally:
        conn.close()

    print(f"Order {n} results ({db_path})")
    print(f"  status: {status}")
    print(f"  graphs_checked: {graphs_checked}")
    print(f"  n_minus_1_in_spectrum: {n_minus_1_in_spectrum}")
    print(f"  conjecture_holds: {conjecture_holds}")
    print(f"  violations: {conjecture_violations}")
    print(f"  not_applicable: {not_applicable}")
    if violations:
        print("  VIOLATION GRAPHS:")
        for graph6, spectrum in violations:
            print(f"    {graph6}: spectrum={spectrum}")


if __name__ == "__main__":
    import sys

    print_summary(sys.argv[1])
