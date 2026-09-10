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
