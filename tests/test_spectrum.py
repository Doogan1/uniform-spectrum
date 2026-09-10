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
