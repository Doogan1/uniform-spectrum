# Uniform Spectrum MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a validated, single-threaded pipeline that computes the uniform spectrum of any graph via a C++ core exposed to Python, and exhaustively re-verifies the "n-1 in spectrum implies n-2 in spectrum" conjecture on all non-isomorphic graphs up to order 8 — matching and superseding the prior manual verification.

**Architecture:** A C++ core (`core/`) implements a pruned bitmask-DFS algorithm to compute a single graph's uniform spectrum from a graph6 string, exposed to Python via pybind11. A Python layer (`py/`) drives `nauty`'s `geng` to stream every non-isomorphic graph of a given order, calls the C++ core per graph, checks the conjecture, and records results with checkpoint/resume into a SQLite database per order.

**Tech Stack:** C++17 (core algorithm), pybind11 (Python bindings), CMake (build), Python 3.10+ (orchestration — code uses PEP 604 `X | None` type hints; this machine has 3.14), `networkx` (cross-validation oracle only, not the runtime path), `nauty`/`geng` (external graph generator), SQLite (results storage), pytest (testing).

**Spec:** `docs/superpowers/specs/2026-09-09-uniform-spectrum-design.md`

## Global Constraints

- Graph order is limited to `n <= 62` (single-byte graph6 header); larger `n` raises a clear error rather than silently misparsing. This ceiling is far above anything exhaustive search will reach.
- Results storage is one SQLite database per order under `results/` (gitignored — this is generated data, not source).
- Per-graph spectrum detail is stored only for conjecture violations, never for every graph checked (would be wasteful at 12,346+ graphs per order).
- All testing is via `pytest` calling into the compiled pybind11 extension — no separate C++ test framework/binary.
- The conjecture is only meaningful for `n >= 3` (for `n < 3`, `n-2 <= 0` is outside the valid spectrum range `1..n-1`); checks for `n < 3` are reported as "not applicable," never as a pass or violation.
- This plan covers Stage 1 (bring-up) and Stage 2 (validate through order 8) of the spec's roadmap only. Pushing past order 8, adding parallelism, the Stage-2 targeted/randomized search, and the subset-DP fallback algorithm are explicitly out of scope here — they depend on runtime data this plan's final task produces, and should be planned separately once that data exists.

## Environment Setup (one-time, verified on this machine)

This machine currently has none of the toolchain installed. Run once, before Task 1:

```bash
sudo dnf install cmake gcc-c++ nauty
python3 -m venv .venv
source .venv/bin/activate
```

(`nauty` on Fedora installs `geng` directly at `/usr/bin/geng` — confirmed via `dnf provides '*/geng'`. `python3 -m venv` bundles its own `pip` even though there is no system-wide `pip`.)

Every subsequent command in this plan assumes the venv is activated (`source .venv/bin/activate`).

---

### Task 1: Graph representation and graph6 parsing (C++ core, build system)

**Files:**
- Create: `core/CMakeLists.txt`
- Create: `core/include/graph.hpp`
- Create: `core/include/graph6.hpp`
- Create: `core/src/graph6.cpp`
- Create: `core/src/bindings.cpp`
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Modify: `.gitignore` (add `.venv/`)
- Test: `tests/test_graph6.py`

**Interfaces:**
- Produces: C++ `struct Graph { int n; std::vector<uint64_t> adj; void add_edge(int u, int v); }` (`core/include/graph.hpp`)
- Produces: C++ `Graph parse_graph6(const std::string& s)` (`core/include/graph6.hpp`), throws `std::invalid_argument` on malformed/unsupported (`n > 62`) input.
- Produces: Python-visible `uniform_spectrum_core.parse_graph6_edges(g6: str) -> list[tuple[int, int]]` (edges as `(u, v)` with `u < v`).
- Produces: `tests/conftest.py` inserts repo root and `core/build/` onto `sys.path` for every test in the suite.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_graph6.py
import networkx as nx

import uniform_spectrum_core as core


def to_graph6(G: "nx.Graph") -> str:
    return nx.to_graph6_bytes(G, header=False).decode().strip()


def edge_set(pairs):
    return {tuple(sorted(p)) for p in pairs}


def test_empty_graph_four_vertices():
    g6 = to_graph6(nx.empty_graph(4))
    assert core.parse_graph6_edges(g6) == []


def test_complete_graph_four_vertices():
    G = nx.complete_graph(4)
    g6 = to_graph6(G)
    assert edge_set(core.parse_graph6_edges(g6)) == edge_set(G.edges())


def test_path_graph_two_vertices():
    G = nx.path_graph(2)
    g6 = to_graph6(G)
    assert edge_set(core.parse_graph6_edges(g6)) == edge_set(G.edges())


def test_petersen_graph():
    G = nx.petersen_graph()
    g6 = to_graph6(G)
    assert edge_set(core.parse_graph6_edges(g6)) == edge_set(G.edges())
```

```python
# tests/conftest.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core" / "build"))
```

```
# tests/__init__.py
(empty file)
```

```
# requirements.txt
pybind11>=2.12
networkx>=3.0
pytest>=7.0
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pip install -r requirements.txt
python -m pytest tests/test_graph6.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'uniform_spectrum_core'`

- [ ] **Step 3: Write the implementation**

```cpp
// core/include/graph.hpp
#pragma once

#include <cstdint>
#include <vector>

struct Graph {
    int n;
    std::vector<uint64_t> adj;

    explicit Graph(int n_) : n(n_), adj(static_cast<size_t>(n_), 0) {}

    void add_edge(int u, int v) {
        adj[static_cast<size_t>(u)] |= (uint64_t(1) << v);
        adj[static_cast<size_t>(v)] |= (uint64_t(1) << u);
    }
};
```

```cpp
// core/include/graph6.hpp
#pragma once

#include <string>

#include "graph.hpp"

Graph parse_graph6(const std::string& s);
```

```cpp
// core/src/graph6.cpp
#include "graph6.hpp"

#include <stdexcept>

Graph parse_graph6(const std::string& s) {
    if (s.empty()) {
        throw std::invalid_argument("empty graph6 string");
    }
    if (s[0] == '~') {
        throw std::invalid_argument("graph6 strings with n > 62 are not supported");
    }

    int n = static_cast<int>(static_cast<unsigned char>(s[0])) - 63;
    if (n < 0 || n > 62) {
        throw std::invalid_argument("invalid graph6 header byte");
    }

    Graph g(n);

    size_t byte_index = 1;
    int bits_left_in_byte = 0;
    uint8_t current_byte = 0;

    auto next_bit = [&]() -> int {
        if (bits_left_in_byte == 0) {
            if (byte_index >= s.size()) {
                throw std::invalid_argument("graph6 string truncated");
            }
            int raw = static_cast<int>(static_cast<unsigned char>(s[byte_index++])) - 63;
            if (raw < 0 || raw > 63) {
                throw std::invalid_argument("invalid graph6 data byte");
            }
            current_byte = static_cast<uint8_t>(raw);
            bits_left_in_byte = 6;
        }
        bits_left_in_byte--;
        return (current_byte >> bits_left_in_byte) & 1;
    };

    for (int x = 1; x < n; x++) {
        for (int y = 0; y < x; y++) {
            if (next_bit()) {
                g.add_edge(x, y);
            }
        }
    }

    return g;
}
```

```cpp
// core/src/bindings.cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <utility>
#include <vector>

#include "graph.hpp"
#include "graph6.hpp"

namespace py = pybind11;

namespace {

std::vector<std::pair<int, int>> parse_graph6_edges(const std::string& g6) {
    Graph g = parse_graph6(g6);
    std::vector<std::pair<int, int>> edges;
    for (int u = 0; u < g.n; u++) {
        uint64_t above_u = ~((uint64_t(1) << (u + 1)) - 1);
        uint64_t neighbors = g.adj[static_cast<size_t>(u)] & above_u;
        while (neighbors) {
            int v = __builtin_ctzll(neighbors);
            neighbors &= neighbors - 1;
            edges.emplace_back(u, v);
        }
    }
    return edges;
}

}  // namespace

PYBIND11_MODULE(uniform_spectrum_core, m) {
    m.def("parse_graph6_edges", &parse_graph6_edges,
          "Parse a graph6 string and return its edges as (u, v) pairs with u < v");
}
```

```cmake
# core/CMakeLists.txt
cmake_minimum_required(VERSION 3.15)
project(uniform_spectrum_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(pybind11 CONFIG REQUIRED)

add_library(spectrum_core STATIC
    src/graph6.cpp
)
target_include_directories(spectrum_core PUBLIC include)

pybind11_add_module(uniform_spectrum_core src/bindings.cpp)
target_link_libraries(uniform_spectrum_core PRIVATE spectrum_core)
```

Also append `.venv/` as a new line to `.gitignore`.

Also add to `README.md` (append a "Setup" section):

```markdown
## Setup

```bash
sudo dnf install cmake gcc-c++ nauty   # geng, cmake, g++ (Fedora)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cmake -S core -B core/build -Dpybind11_DIR=$(python -m pybind11 --cmakedir)
cmake --build core/build
python -m pytest
```
```

- [ ] **Step 4: Build the extension and run the test to verify it passes**

Run:
```bash
cmake -S core -B core/build -Dpybind11_DIR=$(python -m pybind11 --cmakedir)
cmake --build core/build
python -m pytest tests/test_graph6.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add core/ requirements.txt tests/__init__.py tests/conftest.py tests/test_graph6.py README.md .gitignore
git commit -m "Add graph representation and graph6 parser with pybind11 build"
```

(Also add `core/build/` to `.gitignore` if not already covered by the existing `build/` entry — check first with `git status` after the build.)

---

### Task 2: Uniform spectrum algorithm (pruned DFS)

**Files:**
- Create: `core/include/spectrum.hpp`
- Create: `core/src/spectrum.cpp`
- Modify: `core/src/bindings.cpp` (add `spectrum_from_graph6` binding)
- Modify: `core/CMakeLists.txt` (add `src/spectrum.cpp` to `spectrum_core`)
- Create: `tests/legacy_networkx_spectrum.py`
- Test: `tests/test_spectrum.py`

**Interfaces:**
- Consumes: `Graph` and `parse_graph6` from Task 1 (`core/include/graph.hpp`, `core/include/graph6.hpp`).
- Produces: C++ `std::set<int> uniform_spectrum(const Graph& g)` (`core/include/spectrum.hpp`).
- Produces: Python-visible `uniform_spectrum_core.spectrum_from_graph6(g6: str) -> set[int]`.
- Produces: `tests.legacy_networkx_spectrum.legacy_uniform_spectrum(G: nx.Graph) -> set[int]`, used as the cross-validation oracle by this task and Task 3.

- [ ] **Step 1: Write the failing test**

```python
# tests/legacy_networkx_spectrum.py
"""Reference implementation ported from the original networkx-based algorithm
(github.com/Doogan1/Graph-Research-and-Algorithms, 'Uniform Spectrum/main.py'),
used as an independent oracle for cross-validation against the new C++ core."""

from functools import reduce

import networkx as nx


def legacy_uniform_spectrum(G: "nx.Graph") -> set:
    node_set = G.nodes()
    pairs_of_nodes = {(x, y) for x in node_set for y in node_set if x < y}
    if not pairs_of_nodes:
        return set()
    paths = {}
    for (u, v) in pairs_of_nodes:
        paths[(u, v)] = set(map(len, list(nx.all_simple_paths(G, u, v))))
    lengths = reduce(lambda a, b: a.intersection(b), paths.values())
    return {length - 1 for length in lengths}
```

```python
# tests/test_spectrum.py
import networkx as nx
import pytest

import uniform_spectrum_core as core
from tests.legacy_networkx_spectrum import legacy_uniform_spectrum


def to_graph6(G: "nx.Graph") -> str:
    return nx.to_graph6_bytes(G, header=False).decode().strip()


@pytest.mark.parametrize("n", [3, 4, 5])
def test_complete_graph_full_spectrum(n):
    g6 = to_graph6(nx.complete_graph(n))
    assert core.spectrum_from_graph6(g6) == set(range(1, n))


def test_path_graph_two_vertices_spectrum_is_single_edge_length():
    g6 = to_graph6(nx.path_graph(2))
    assert core.spectrum_from_graph6(g6) == {1}


@pytest.mark.parametrize("n", [4, 6])
def test_path_graph_spectrum_is_empty(n):
    g6 = to_graph6(nx.path_graph(n))
    assert core.spectrum_from_graph6(g6) == set()


@pytest.mark.parametrize("n", [4, 5])
def test_cycle_graph_spectrum_is_empty(n):
    g6 = to_graph6(nx.cycle_graph(n))
    assert core.spectrum_from_graph6(g6) == set()


def test_petersen_graph_matches_legacy_implementation():
    G = nx.petersen_graph()
    g6 = to_graph6(G)
    assert core.spectrum_from_graph6(g6) == legacy_uniform_spectrum(G)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_spectrum.py -v`
Expected: FAIL with `AttributeError: module 'uniform_spectrum_core' has no attribute 'spectrum_from_graph6'`

- [ ] **Step 3: Write the implementation**

```cpp
// core/include/spectrum.hpp
#pragma once

#include <set>

#include "graph.hpp"

std::set<int> uniform_spectrum(const Graph& g);
```

```cpp
// core/src/spectrum.cpp
#include "spectrum.hpp"

namespace {

// DFS from `cur` toward `target`, tracking which lengths (edge counts) have
// been achieved so far in `achieved`. Stops a branch as soon as every length
// still relevant to the running spectrum intersection (`target_mask`) has
// been found for this pair -- we only need existence, never enumeration.
void dfs(const Graph& g, int cur, int target, uint64_t visited, int length,
         uint64_t& achieved, uint64_t target_mask) {
    if (cur == target) {
        if (length > 0) {
            achieved |= (uint64_t(1) << length);
        }
        return;
    }
    if ((achieved & target_mask) == target_mask) {
        return;
    }
    uint64_t candidates = g.adj[static_cast<size_t>(cur)] & ~visited;
    while (candidates) {
        int next = __builtin_ctzll(candidates);
        candidates &= candidates - 1;
        dfs(g, next, target, visited | (uint64_t(1) << next), length + 1, achieved, target_mask);
        if ((achieved & target_mask) == target_mask) {
            return;
        }
    }
}

}  // namespace

std::set<int> uniform_spectrum(const Graph& g) {
    int n = g.n;
    uint64_t spectrum_mask = 0;
    for (int k = 1; k <= n - 1; k++) {
        spectrum_mask |= (uint64_t(1) << k);
    }

    for (int u = 0; u < n && spectrum_mask != 0; u++) {
        for (int v = u + 1; v < n && spectrum_mask != 0; v++) {
            uint64_t achieved = 0;
            dfs(g, u, v, (uint64_t(1) << u), 0, achieved, spectrum_mask);
            spectrum_mask &= achieved;
        }
    }

    std::set<int> result;
    for (int k = 1; k <= n - 1; k++) {
        if (spectrum_mask & (uint64_t(1) << k)) {
            result.insert(k);
        }
    }
    return result;
}
```

Modify `core/src/bindings.cpp`: add the include and binding.

```cpp
// core/src/bindings.cpp  (add near the top, with the other includes)
#include "spectrum.hpp"
```

```cpp
// core/src/bindings.cpp  (add inside the anonymous namespace, after parse_graph6_edges)
std::set<int> spectrum_from_graph6(const std::string& g6) {
    Graph g = parse_graph6(g6);
    return uniform_spectrum(g);
}
```

```cpp
// core/src/bindings.cpp  (add inside PYBIND11_MODULE, after the parse_graph6_edges binding)
    m.def("spectrum_from_graph6", &spectrum_from_graph6,
          "Compute the uniform spectrum of a graph given as a graph6 string");
```

Modify `core/CMakeLists.txt`:

```cmake
# core/CMakeLists.txt  (change the add_library call to)
add_library(spectrum_core STATIC
    src/graph6.cpp
    src/spectrum.cpp
)
```

- [ ] **Step 4: Rebuild and run test to verify it passes**

Run:
```bash
cmake --build core/build
python -m pytest tests/test_spectrum.py -v
```
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add core/include/spectrum.hpp core/src/spectrum.cpp core/src/bindings.cpp core/CMakeLists.txt tests/legacy_networkx_spectrum.py tests/test_spectrum.py
git commit -m "Add pruned-DFS uniform spectrum algorithm"
```

---

### Task 3: geng wrapper and exhaustive cross-validation (orders 1-6)

**Files:**
- Create: `py/__init__.py`
- Create: `py/generate.py`
- Test: `tests/test_generate.py`
- Test: `tests/test_cross_validation.py`

**Interfaces:**
- Consumes: `uniform_spectrum_core.spectrum_from_graph6` (Task 2), `tests.legacy_networkx_spectrum.legacy_uniform_spectrum` (Task 2).
- Produces: `py.generate.run_geng(n: int) -> Iterator[str]`, yielding one graph6 string per non-isomorphic graph of order `n`.

- [ ] **Step 1: Write the failing test**

```python
# py/__init__.py
(empty file)
```

```python
# tests/test_generate.py
from py import generate

# Known counts of non-isomorphic graphs by order (OEIS A000088)
EXPECTED_COUNTS = {1: 1, 2: 2, 3: 4, 4: 11, 5: 34, 6: 156}


def test_run_geng_produces_expected_counts():
    for n, expected in EXPECTED_COUNTS.items():
        graphs = list(generate.run_geng(n))
        assert len(graphs) == expected, f"order {n}: expected {expected}, got {len(graphs)}"


def test_run_geng_yields_non_empty_strings():
    for g6 in generate.run_geng(4):
        assert g6.strip() != ""
```

```python
# tests/test_cross_validation.py
import networkx as nx
import pytest

import uniform_spectrum_core as core
from py import generate
from tests.legacy_networkx_spectrum import legacy_uniform_spectrum


def graph6_to_networkx(g6: str) -> "nx.Graph":
    return nx.from_graph6_bytes(g6.encode())


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6])
def test_core_matches_legacy_for_all_graphs_of_order(n):
    for g6 in generate.run_geng(n):
        G = graph6_to_networkx(g6)
        assert core.spectrum_from_graph6(g6) == legacy_uniform_spectrum(G), (
            f"mismatch for graph6={g6!r} at order {n}"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_generate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'py'` (or `py.generate`)

- [ ] **Step 3: Write the implementation**

```python
# py/generate.py
"""Streams non-isomorphic graphs of a given order using nauty's geng."""

import shutil
import subprocess
from typing import Iterator

GENG_CANDIDATES = ["geng", "nauty-geng"]


def _find_geng() -> str:
    for name in GENG_CANDIDATES:
        if shutil.which(name):
            return name
    raise RuntimeError(
        "Could not find a `geng` binary (tried: "
        + ", ".join(GENG_CANDIDATES)
        + "). Install nauty (e.g. `sudo dnf install nauty` on Fedora, "
        "or build from https://pallini.di.uniroma1.it/) and ensure "
        "its geng binary is on PATH."
    )


def run_geng(n: int) -> Iterator[str]:
    """Yield one graph6 string per non-isomorphic graph of order n."""
    binary = _find_geng()
    proc = subprocess.Popen(
        [binary, str(n)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            line = line.strip()
            if line:
                yield line
    finally:
        proc.stdout.close()
        returncode = proc.wait()
        if returncode != 0:
            raise RuntimeError(f"geng exited with code {returncode}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_generate.py tests/test_cross_validation.py -v`
Expected: PASS (all tests; `test_cross_validation.py` exhaustively checks 1+2+4+11+34+156 = 208 graphs and may take a few seconds)

- [ ] **Step 5: Commit**

```bash
git add py/__init__.py py/generate.py tests/test_generate.py tests/test_cross_validation.py
git commit -m "Add geng wrapper and exhaustive cross-validation up to order 6"
```

---

### Task 4: Conjecture check

**Files:**
- Create: `py/conjecture.py`
- Test: `tests/test_conjecture.py`

**Interfaces:**
- Produces: `py.conjecture.check(n: int, spectrum: set[int]) -> bool | None` — `True` if the conjecture holds for this graph, `False` if it's violated, `None` if not applicable (`n < 3`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_conjecture.py
from py import conjecture


def test_holds_when_n_minus_1_not_in_spectrum():
    assert conjecture.check(5, {1, 2}) is True


def test_holds_when_both_n_minus_1_and_n_minus_2_present():
    assert conjecture.check(5, {1, 2, 3, 4}) is True


def test_violation_when_n_minus_1_present_but_n_minus_2_absent():
    assert conjecture.check(5, {1, 4}) is False


def test_not_applicable_for_n_less_than_three():
    assert conjecture.check(1, set()) is None
    assert conjecture.check(2, {1}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_conjecture.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'py.conjecture'`

- [ ] **Step 3: Write the implementation**

```python
# py/conjecture.py
"""Checks the conjecture: if n-1 is in a graph's uniform spectrum, n-2 must be too."""


def check(n: int, spectrum: set) -> bool | None:
    if n < 3:
        return None
    if (n - 1) in spectrum:
        return (n - 2) in spectrum
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_conjecture.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add py/conjecture.py tests/test_conjecture.py
git commit -m "Add conjecture check"
```

---

### Task 5: Batch driver with SQLite checkpoint/resume

**Files:**
- Create: `py/driver.py`
- Test: `tests/test_driver.py`

**Interfaces:**
- Consumes: `py.generate.run_geng` (Task 3), `uniform_spectrum_core.spectrum_from_graph6` (Task 2), `py.conjecture.check` (Task 4).
- Produces: `py.driver.init_db(conn, n: int) -> None`, `py.driver.get_progress(conn) -> tuple[int, str]`, `py.driver.record_result(conn, index: int, graph6: str, spectrum: set[int], n_minus_1_in_spectrum: bool, holds: bool | None) -> None`, `py.driver.mark_complete(conn) -> None`, `py.driver.run(n: int, db_path, checkpoint_interval: int = 1000) -> None`.
- SQLite schema (per order, one file `results/order_N.sqlite`): `progress(id, n, last_index, status)`, `violations(graph6, spectrum, found_at)`, `summary(id, graphs_checked, n_minus_1_in_spectrum, conjecture_holds, conjecture_violations, not_applicable)` — `progress` and `summary` are singleton rows (`id = 0`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_driver.py
import subprocess
import sqlite3
import sys
from pathlib import Path

from py import driver

# Order-4 has 11 non-isomorphic graphs (OEIS A000088); indices 0..10.
ORDER_4_GRAPH_COUNT = 11

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_cli_invocation_runs_as_standalone_script(tmp_path):
    # Regression test: driver.py is invoked as `python py/driver.py N` (not
    # via pytest) in Task 7 and the README. Running it this way puts py/'s
    # own directory on sys.path, not the repo root, so `from py import ...`
    # inside driver.py must not depend on pytest's conftest.py path setup.
    db_path = tmp_path / "order4.sqlite"
    result = subprocess.run(
        [sys.executable, "py/driver.py", "4", "--db", str(db_path)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr
    assert db_path.exists()


def test_full_run_order4(tmp_path):
    db_path = tmp_path / "order4.sqlite"
    driver.run(4, db_path)

    conn = sqlite3.connect(db_path)
    last_index, status = driver.get_progress(conn)
    graphs_checked = conn.execute(
        "SELECT graphs_checked FROM summary WHERE id = 0"
    ).fetchone()[0]
    violations = conn.execute("SELECT COUNT(*) FROM violations").fetchone()[0]
    conn.close()

    assert status == "complete"
    assert last_index == ORDER_4_GRAPH_COUNT - 1
    assert graphs_checked == ORDER_4_GRAPH_COUNT
    assert violations == 0


def test_run_is_noop_when_already_complete(tmp_path):
    db_path = tmp_path / "order4.sqlite"
    driver.run(4, db_path)

    conn = sqlite3.connect(db_path)
    first_count = conn.execute(
        "SELECT graphs_checked FROM summary WHERE id = 0"
    ).fetchone()[0]
    conn.close()

    driver.run(4, db_path)  # should be a no-op

    conn = sqlite3.connect(db_path)
    second_count = conn.execute(
        "SELECT graphs_checked FROM summary WHERE id = 0"
    ).fetchone()[0]
    status = conn.execute("SELECT status FROM progress WHERE id = 0").fetchone()[0]
    conn.close()

    assert first_count == ORDER_4_GRAPH_COUNT
    assert second_count == ORDER_4_GRAPH_COUNT
    assert status == "complete"


def test_run_resumes_from_partial_progress(tmp_path):
    db_path = tmp_path / "order4.sqlite"
    conn = sqlite3.connect(db_path)
    driver.init_db(conn, 4)
    for i in range(6):
        driver.record_result(conn, i, f"fake-graph-{i}", set(), False, True)
    conn.commit()
    conn.close()

    driver.run(4, db_path)

    conn = sqlite3.connect(db_path)
    last_index, status = driver.get_progress(conn)
    graphs_checked = conn.execute(
        "SELECT graphs_checked FROM summary WHERE id = 0"
    ).fetchone()[0]
    conn.close()

    assert status == "complete"
    assert last_index == ORDER_4_GRAPH_COUNT - 1
    assert graphs_checked == ORDER_4_GRAPH_COUNT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_driver.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'py.driver'`

- [ ] **Step 3: Write the implementation**

```python
# py/driver.py
"""Batch-checks the uniform spectrum conjecture across all graphs of one order."""

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
            (graph6, repr(sorted(spectrum)), datetime.now(timezone.utc).isoformat()),
        )


def mark_complete(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE progress SET status = 'complete' WHERE id = 0")


def run(n: int, db_path, checkpoint_interval: int = DEFAULT_CHECKPOINT_INTERVAL) -> None:
    conn = sqlite3.connect(db_path)
    try:
        init_db(conn, n)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_driver.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add py/driver.py tests/test_driver.py
git commit -m "Add SQLite-backed batch driver with checkpoint/resume"
```

---

### Task 6: Results summary reporter

**Files:**
- Create: `py/analyze.py`
- Test: `tests/test_analyze.py`

**Interfaces:**
- Consumes: the `progress`/`summary`/`violations` schema from Task 5.
- Produces: `py.analyze.print_summary(db_path) -> None`, printing a human-readable report to stdout.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_analyze.py
from py import analyze, driver


def test_print_summary_reports_counts(tmp_path, capsys):
    db_path = tmp_path / "order4.sqlite"
    driver.run(4, db_path)

    analyze.print_summary(db_path)

    out = capsys.readouterr().out
    assert "Order 4" in out
    assert "status: complete" in out
    assert "graphs_checked: 11" in out
    assert "violations: 0" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_analyze.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'py.analyze'`

- [ ] **Step 3: Write the implementation**

```python
# py/analyze.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_analyze.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add py/analyze.py tests/test_analyze.py
git commit -m "Add results summary reporter"
```

---

### Task 7: Exhaustive conjecture verification through order 8

**Files:**
- Create: `pytest.ini`
- Test: `tests/test_conjecture_regression.py`
- Create: `docs/results.md`

**Interfaces:**
- Consumes: `py.driver.run` (Task 5), `py.analyze.print_summary` (Task 6).

- [ ] **Step 1: Write the failing test**

```ini
# pytest.ini
[pytest]
markers =
    slow: exhaustive tests over larger graph orders (order 8+)
```

```python
# tests/test_conjecture_regression.py
import sqlite3

import pytest

from py import driver

# Non-isomorphic graph counts by order (OEIS A000088)
GRAPH_COUNTS = {3: 4, 4: 11, 5: 34, 6: 156, 7: 1044, 8: 12346}


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7])
def test_no_conjecture_violations(tmp_path, n):
    db_path = tmp_path / f"order{n}.sqlite"
    driver.run(n, db_path)
    conn = sqlite3.connect(db_path)
    graphs_checked = conn.execute("SELECT graphs_checked FROM summary WHERE id = 0").fetchone()[0]
    violations = conn.execute("SELECT COUNT(*) FROM violations").fetchone()[0]
    conn.close()
    assert graphs_checked == GRAPH_COUNTS[n]
    assert violations == 0


@pytest.mark.slow
def test_no_conjecture_violations_order8(tmp_path):
    n = 8
    db_path = tmp_path / "order8.sqlite"
    driver.run(n, db_path)
    conn = sqlite3.connect(db_path)
    graphs_checked = conn.execute("SELECT graphs_checked FROM summary WHERE id = 0").fetchone()[0]
    violations = conn.execute("SELECT COUNT(*) FROM violations").fetchone()[0]
    conn.close()
    assert graphs_checked == GRAPH_COUNTS[n]
    assert violations == 0
```

This task is a regression check over functionality Tasks 1-6 already built and tested — there is no new implementation gap to close, so there's no red step: run it and it should already pass.

- [ ] **Step 2: Run the fast orders (3-7) and verify they pass**

Run: `python -m pytest tests/test_conjecture_regression.py -v -m "not slow"`
Expected: PASS for orders 3, 4, 5, 6, 7 — zero violations in every case.

- [ ] **Step 3: Run order 8 and verify it passes**

Run: `python -m pytest tests/test_conjecture_regression.py -v -m "slow"`
Expected: PASS — zero violations at order 8.

If any assertion fails at any order (a violation found, or a count mismatch), STOP — do not proceed to Step 4. A count mismatch means a bug in `generate.py` or `driver.py`; a violation means either a counterexample to the conjecture (extremely significant — report immediately, do not treat as a bug to silently fix) or a bug in the spectrum algorithm. Re-run `tests/test_spectrum.py` and `tests/test_cross_validation.py` to narrow it down before touching anything else.

- [ ] **Step 4: Run the real milestone commands and record results**

```bash
mkdir -p docs
for n in 3 4 5 6 7 8; do
  python py/driver.py "$n"
done
{
  echo "# Results: exhaustive verification through order 8"
  echo
  echo "Produced by \`py/driver.py\`, re-verifying the conjecture"
  echo "(\"n-1 in spectrum implies n-2 in spectrum\") exhaustively over"
  echo "all non-isomorphic graphs of each order."
  echo
  echo '```'
  for n in 3 4 5 6 7 8; do
    python py/analyze.py "results/order_$n.sqlite"
    echo
  done
  echo '```'
} > docs/results.md
```

Open `docs/results.md` and confirm it shows zero violations for every order 3 through 8.

- [ ] **Step 5: Commit**

```bash
git add pytest.ini tests/test_conjecture_regression.py docs/results.md
git commit -m "Add exhaustive conjecture regression tests through order 8, record results"
```

---

## Self-Review Notes

- **Spec coverage:** Core algorithm (spec "Algorithm" section) → Task 2. `geng`/graph6 pipeline (spec "Architecture") → Tasks 1, 3. pybind11 boundary (spec "Architecture") → Tasks 1, 2. SQLite checkpoint/resume schema (spec "Results storage & checkpointing") → Task 5. Testing strategy (spec "Testing & validation") → Tasks 2, 3, 7. Roadmap steps 1-2 (bring-up, validate through order 8) → all tasks; steps 3-5 (push past 8, targeted search, DP fallback) are explicitly deferred per the Global Constraints and spec's own conditional phrasing.
- **Not in this plan, by design:** parallelism/`--split`, order 9+, the subset-DP fallback, and Stage-2 targeted/randomized search. These depend on the timing data Task 7 produces and should be scoped as a follow-up plan once that data exists.
