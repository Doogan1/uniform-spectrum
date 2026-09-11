# py/query.py
"""Query per-graph detail data recorded by `driver.py --record-details`."""

import json
import sqlite3
import sys
from pathlib import Path

_SORT_KEYS = {
    "graph6": lambda row: row[0],
    "spectrum_size": lambda row: len(row[1]),
    "compute_seconds": lambda row: row[2],
}


def query_graphs(
    db_path,
    spectrum_size=None,
    min_size=None,
    max_size=None,
    contains=None,
    not_contains=None,
    sort="graph6",
    desc=False,
):
    """Return matching rows from graph_results as (graph6, spectrum, compute_seconds),
    filtered (all filters AND together) and sorted. `spectrum` is a list of ints."""
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"No such database: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        try:
            cursor = conn.execute("SELECT graph6, spectrum, compute_seconds FROM graph_results")
        except sqlite3.OperationalError as e:
            raise RuntimeError(
                f"{db_path} has no graph_results table. Was it created with "
                f"`driver.py --record-details`?"
            ) from e

        results = []
        for graph6, spectrum_json, compute_seconds in cursor:
            spectrum = json.loads(spectrum_json)
            size = len(spectrum)
            if spectrum_size is not None and size != spectrum_size:
                continue
            if min_size is not None and size < min_size:
                continue
            if max_size is not None and size > max_size:
                continue
            if contains is not None and contains not in spectrum:
                continue
            if not_contains is not None and not_contains in spectrum:
                continue
            results.append((graph6, spectrum, compute_seconds))
    finally:
        conn.close()

    results.sort(key=_SORT_KEYS[sort], reverse=desc)
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Query per-graph detail data recorded by `driver.py --record-details`."
    )
    parser.add_argument("db", type=str, help="path to a results sqlite database")
    parser.add_argument("--spectrum-size", type=int, default=None, help="exact spectrum size")
    parser.add_argument("--min-size", type=int, default=None, help="minimum spectrum size (inclusive)")
    parser.add_argument("--max-size", type=int, default=None, help="maximum spectrum size (inclusive)")
    parser.add_argument("--contains", type=int, default=None, help="spectrum must contain this value")
    parser.add_argument(
        "--not-contains", type=int, default=None, help="spectrum must not contain this value"
    )
    parser.add_argument(
        "--sort", choices=["graph6", "spectrum_size", "compute_seconds"], default="graph6"
    )
    parser.add_argument("--desc", action="store_true", help="sort descending instead of ascending")
    parser.add_argument("--limit", type=int, default=None, help="limit number of rows printed")
    parser.add_argument(
        "--count", action="store_true", help="print only the match count, not the rows (ignores --limit)"
    )
    args = parser.parse_args()

    try:
        results = query_graphs(
            args.db,
            spectrum_size=args.spectrum_size,
            min_size=args.min_size,
            max_size=args.max_size,
            contains=args.contains,
            not_contains=args.not_contains,
            sort=args.sort,
            desc=args.desc,
        )
    except (FileNotFoundError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.count:
            print(len(results))
        else:
            display = results[: args.limit] if args.limit is not None else results
            for graph6, spectrum, compute_seconds in display:
                print(f"{graph6}\t{spectrum}\t{compute_seconds:.6f}")
    except BrokenPipeError:
        # Piping into `head`, `less -q`, etc. closes stdin early -- that's not
        # an error, so exit quietly instead of dumping a traceback.
        import os

        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(0)
