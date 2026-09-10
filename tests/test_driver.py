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
