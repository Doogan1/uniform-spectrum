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
