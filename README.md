# uniform-spectrum

Computing the uniform spectrum of graphs, and hunting for a counterexample
(or more evidence) for a conjecture: if `n-1` is in the uniform spectrum of
a graph of order `n`, is `n-2` always in it too?

See [`docs/superpowers/specs/2026-09-09-uniform-spectrum-design.md`](docs/superpowers/specs/2026-09-09-uniform-spectrum-design.md)
for the full design.

## Setup

```bash
sudo dnf install cmake gcc-c++ nauty   # geng, cmake, g++ (Fedora)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cmake -S core -B core/build -Dpybind11_DIR=$(python -m pybind11 --cmakedir)
cmake --build core/build
# Use `python -m pytest`, not bare `pytest` -- this project's py/ package
# collides with a pytest-internal compatibility shim otherwise (see
# py/__init__.py for why).
python -m pytest
```

## Usage

### Exhaustively check every graph of a given order

`py/driver.py` drives `geng` to generate every non-isomorphic graph of
order `n`, checks the conjecture on each, and records results (with
checkpoint/resume) into a SQLite database:

```bash
python py/driver.py 9
```

By default this writes to `results/order_9.sqlite` (pass `--db path/to/file.sqlite`
to use a different location). If it's interrupted partway through, just run
the same command again — it picks up from the last checkpoint instead of
starting over.

To see a summary once it's done (or check progress on a still-running order):

```bash
python py/analyze.py results/order_9.sqlite
```

This prints the graph count checked, how many had `n-1` in their spectrum,
and any conjecture violations found (there shouldn't be any — see
[`docs/results.md`](docs/results.md) for orders 3-8, verified with zero
violations across all 13,595 graphs).

A rough sense of scale (non-isomorphic graph counts, [OEIS A000088](https://oeis.org/A000088)):
order 8 has 12,346 graphs and ran in 0.42s on a laptop; order 9 has 274,668
and is expected to finish well under a minute, single-threaded, with no
special hardware needed.

### Recording per-graph data for research queries

By default the database above only stores aggregate counts (how many graphs
had `n-1` in their spectrum, how many violated the conjecture, etc.) — not
the full spectrum of every graph, since that would be a lot of data at large
orders for no benefit in the common case. If you want to dig into the
per-graph data directly (e.g. "find every order-9 graph with a singleton
spectrum"), pass `--record-details`:

```bash
python py/driver.py 9 --record-details
```

This populates a `graph_results` table with one row per graph: its
[graph6](https://users.cecs.anu.edu.au/~bdm/data/formats.txt) encoding, its
full uniform spectrum (as a JSON array), and how long the algorithm took to
compute that graph's spectrum, in seconds. Query it directly:

```python
import json, sqlite3

conn = sqlite3.connect("results/order_9.sqlite")
for graph6, spectrum_json in conn.execute("SELECT graph6, spectrum FROM graph_results"):
    if len(json.loads(spectrum_json)) == 1:
        print(graph6, spectrum_json)  # every singleton-spectrum graph

total_compute_time = conn.execute("SELECT SUM(compute_seconds) FROM graph_results").fetchone()[0]
```

The command's own printed "this run took ...s" line gives overall wall-clock
time for the run (including graph generation and database writes);
`SUM(compute_seconds)` above gives just the algorithm's own compute time,
which will be smaller.

**Caveat:** if you resume a database that was started *without*
`--record-details` and add the flag partway through, only the graphs
processed *after* that point get detail rows — there's no retroactive
backfill for graphs already checked. If you want full per-graph detail for
an order, pass `--record-details` from that order's very first run.

### Check a single, specific graph

There's no separate CLI script for this yet, but it's a few lines of Python
using the same pieces `driver.py` uses internally. Build your graph however
you like (here, `networkx`), encode it as [graph6](https://users.cecs.anu.edu.au/~bdm/data/formats.txt),
and hand it to the compiled core:

```bash
python3 <<'EOF'
import sys
sys.path.insert(0, ".")
sys.path.insert(0, "core/build")

import networkx as nx
import uniform_spectrum_core as core
from py import conjecture

# Build your graph here -- this example is a 4-cycle.
G = nx.cycle_graph(4)
g6 = nx.to_graph6_bytes(G, header=False).decode().strip()

n = G.number_of_nodes()
spectrum = core.spectrum_from_graph6(g6)

print(f"order {n}, graph6={g6}")
print(f"uniform spectrum: {sorted(spectrum)}")
print(f"conjecture holds: {conjecture.check(n, spectrum)}")
EOF
```

If you already have a graph6 string from elsewhere (nauty's own tools, or
an online converter), skip the `networkx` construction step and pass it to
`core.spectrum_from_graph6(...)` directly — just make sure you also know
its order `n` for the `conjecture.check(n, spectrum)` call.
