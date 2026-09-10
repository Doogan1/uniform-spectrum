import networkx as nx
import pytest

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


def test_graph6_n_greater_than_62_raises_error():
    # Graph6 format uses single-byte header with maximum n=62
    # The '~' prefix indicates n > 62 (extended format not supported)
    with pytest.raises(ValueError):
        core.parse_graph6_edges("~?")
