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
