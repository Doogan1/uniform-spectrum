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
