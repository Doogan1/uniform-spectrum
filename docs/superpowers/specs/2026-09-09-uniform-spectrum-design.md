# Uniform Spectrum Design

## Problem

For a graph `G` of order `n` (vertices `1..n`), the **uniform spectrum** of `G`
is the set of integers `k` such that for *every* pair of distinct vertices
`u, v` in `G`, there exists a simple `u`-`v` path with exactly `k` edges.
`k` ranges over `1..n-1`.

**Conjecture:** if `n-1` is in the uniform spectrum of a graph of order `n`,
then `n-2` is also in the uniform spectrum. No proof or counterexample is
known. The conjecture has been verified by exhaustive check on all graphs of
order up to 8.

## Goal

Reimplement spectrum computation with a real performance budget behind it,
then:

1. Re-verify the conjecture exhaustively (all non-isomorphic graphs) at
   order ≤ 8 as a correctness check on the reimplementation, then push
   exhaustive verification as far past order 8 as is computationally
   feasible (order 9, 10, 11, ...).
2. Once exhaustive search stops being feasible, switch to targeted/
   randomized search on larger orders to keep hunting for a counterexample
   or further evidence for the conjecture.

## Prior work

An earlier Python implementation
([`Graph-Research-and-Algorithms/Uniform Spectrum/main.py`](https://github.com/Doogan1/Graph-Research-and-Algorithms/blob/main/Uniform%20Spectrum/main.py))
computed the spectrum with `networkx`:

```python
def uniform_spectrum(G):
    node_set = G.nodes()
    pairs_of_nodes = {(x,y) for x in node_set for y in node_set if x < y}
    paths = {}
    for (u,v) in pairs_of_nodes:
        paths[(u,v)] = set(map(len,list(nx.all_simple_paths(G, u, v))))
    return list(map(lambda a: a-1,reduce(lambda a, b: b.intersection(a),paths.values())))
```

This enumerates *every* simple path between each pair just to record which
lengths occur, and has no graph-generation, batch-driving, or
conjecture-checking logic — those either lived elsewhere (an empty
`oldSageAlgo.py` in the same repo suggests an earlier SageMath-based version,
and Sage bundles `nauty`) or were never committed. There is no artifact to
reuse beyond the algorithmic idea and the definitions above.

The reimplementation targets two independent sources of the old approach's
cost:

- **Path enumeration is more work than necessary.** For a dense graph,
  the number of simple paths between two vertices can be enormous (on the
  order of `n!` for `Kₙ`), but we only need to know *which lengths are
  achievable*, not enumerate every path realizing them.
- **Isomorph-filtered generation is far more expensive than isomorph-free
  generation.** Generating all labeled graphs and filtering out
  isomorphic duplicates is combinatorially far worse than generating
  each isomorphism class exactly once.

## Algorithm: single-graph spectrum

Represent a graph of order `n` as `n` bitmasks (`adj[v]` = bitmask of `v`'s
neighbors), letting `n` fit in a native integer width (practical ceiling
around n ≤ ~30 for a 32-bit mask, more with 64-bit).

**Approach A — pruned bitmask DFS, existence-only (build this first).**
For each pair `(u, v)`, DFS from `u` tracking a `visited` bitmask and the
current path length. Instead of collecting every path (as the old code
does), maintain a bitset of lengths already confirmed reachable for this
pair and stop exploring a branch once it cannot produce a length not
already found. Once all of `1..n-1` are confirmed for a pair, stop
searching that pair entirely. Worst case is still combinatorial on dense
graphs, but average-case cost drops sharply since we never enumerate more
paths than needed to prove existence of each length.

**Approach B — subset DP (Held–Karp style; fallback, not built initially).**
`reach[S][v]` = true iff a simple path from `u` to `v` exists visiting
exactly the vertex set `S`. Transition: `reach[S][v] = OR over w in S\{v}
with edge(w,v) of reach[S\{v}][w]`. This gives a hard `O(n · 2ⁿ · n²)`
bound per graph regardless of density, at the cost of `O(2ⁿ)` memory per
source vertex and more implementation complexity. Kept as a documented,
not-yet-built alternative backend behind the same core interface, to add
if profiling shows dense graphs dominating runtime at some order.

The graph's uniform spectrum is the intersection, over all pairs, of each
pair's achieved-length set.

## Architecture

```
uniform-spectrum/
├── core/                      # C++ — the hot loop
│   ├── include/graph.hpp      # compact bitmask graph representation
│   ├── src/spectrum.cpp       # pruned-DFS spectrum algorithm (Approach A)
│   ├── src/spectrum_dp.cpp    # subset-DP fallback (Approach B, added later)
│   ├── src/bindings.cpp       # pybind11 bindings: spectrum(graph6_str) -> set[int]
│   └── CMakeLists.txt
├── py/
│   ├── generate.py            # drives `geng`, streams graph6 lines
│   ├── driver.py              # main batch loop: geng -> core -> checkpoint -> results
│   ├── conjecture.py          # checks "n-1 in spectrum => n-2 in spectrum" per graph
│   └── analyze.py             # summarize results, report violations/stats
├── tests/
│   ├── test_core.py           # cross-checks core against known graphs + old networkx impl
│   └── fixtures/              # small hand-verified graphs (K_n, C_n, P_n, Petersen, etc.)
├── results/                   # gitignored — sqlite dbs per order live here
├── docs/
└── README.md
```

**Graph generation:** [`nauty`](https://pallini.di.uniroma1.it/)'s `geng`
generates every non-isomorphic graph of order `n` directly in canonical
form (graph6 text format, one graph per line), so no isomorphism filtering
is needed downstream. This is a system dependency (installed via package
manager or built from nauty's source), not something we reimplement —
writing a competitive canonical graph generator from scratch is itself a
significant research problem, and nauty is the field-standard, decades-
optimized tool for exactly this.

**Python/C++ boundary:** the core is exposed to Python via `pybind11`
(chosen over `ctypes`/`cffi` for clean native-type marshalling — Python
sets and ints in, no manual buffer management). Python owns orchestration:
invoking `geng`, iterating its output, calling into the core per graph,
checking the conjecture, and recording results. C++ owns only the
performance-critical per-graph spectrum computation.

**Pipeline:** `geng n` streams graph6 lines → `driver.py` reads a line →
passes it to the C++ core → core parses it into a bitmask adjacency graph
and returns the spectrum as a set of ints → `conjecture.py` checks
`n-1 ∈ spectrum ⟹ n-2 ∈ spectrum` → result and progress are written to the
order's checkpoint database → loop continues.

**Parallelism:** each graph's check is fully independent of every other
graph, so this is embarrassingly parallel. Multiple worker processes can
each claim a shard of `geng`'s output (via `geng`'s built-in `--split` job
partitioning, or a simple index-mod-N split) and write to their own
checkpoint rows. The initial version is single-threaded, validated for
correctness first; the parallel split is added once that's confirmed, and
is expected to be needed for order 9+ to finish in a reasonable time on a
laptop.

## Results storage & checkpointing

One SQLite database per order, `results/order_N.sqlite`, with three tables:

- **progress** — single row: last graph6 index processed, timestamp,
  status (`running` / `complete`). On restart, `driver.py` reads this and
  resumes generation from that point instead of restarting from scratch.
- **violations** — any graph where the conjecture fails: graph6 string,
  computed spectrum, timestamp. This table should always end up empty;
  a single row here is the headline result of the whole project.
- **summary** — aggregate stats for the order as a whole (graphs checked,
  count where `n-1 ∈ spectrum`, count where the conjecture held, min/max
  spectrum size, etc.). Full per-graph spectra are not stored except for
  violations — storing spectrum detail for every one of, e.g., 12M+ graphs
  at order 10 is neither useful nor cheap.

## Testing & validation

- Unit tests on hand-verified small graphs (`Kₙ`, `Cₙ`, `Pₙ`, the Petersen
  graph, and a handful of hand-picked irregular cases) with known expected
  spectra.
- Cross-validation: run both the old `networkx`-based function and the new
  core across all graphs up to order 7-8 and assert identical results.
  This is the correctness proof for the reimplementation, independent of
  its speed.
- A conjecture-specific regression test: exhaustively re-run order ≤ 8
  with the new tool and confirm zero violations, matching the prior
  "verified up to 8" result, before the tool is trusted at order 9+.

## Roadmap

1. **Bring-up** — core DFS algorithm (Approach A), pybind11 bindings, and
   the `geng`-driven pipeline, single-threaded.
2. **Validate** — cross-check against the old `networkx` implementation
   and confirm order ≤ 8 reproduces "conjecture holds, zero violations."
3. **Push exhaustive** — order 9, then 10, then 11 if feasible, adding the
   parallel split once single-threaded correctness is confirmed.
4. **Stage 2: targeted search** — once exhaustive search is no longer
   practical at the current order ceiling, add randomized/targeted search
   (e.g. random large graphs, or graphs constructed to be near-Hamiltonian-
   connected so that `n-1` is likely already in the spectrum) to keep
   probing for a counterexample beyond the exhaustive ceiling.
5. **Approach B (conditional)** — add the subset-DP backend only if
   profiling during stage 3 shows dense graphs dominating runtime at some
   order.
