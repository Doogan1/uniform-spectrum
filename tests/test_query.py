# tests/test_query.py
import sqlite3
import subprocess
import sys
from pathlib import Path

from py import driver, query

REPO_ROOT = Path(__file__).resolve().parent.parent


def _build_order5_db(tmp_path):
    db_path = tmp_path / "order5.sqlite"
    driver.run(5, db_path, record_details=True)
    return db_path


def test_query_by_exact_spectrum_size(tmp_path):
    db_path = _build_order5_db(tmp_path)
    results = query.query_graphs(db_path, spectrum_size=1)

    assert len(results) > 0
    for graph6, spectrum, compute_seconds in results:
        assert len(spectrum) == 1
        assert compute_seconds >= 0


def test_query_by_min_and_max_size(tmp_path):
    db_path = _build_order5_db(tmp_path)
    results = query.query_graphs(db_path, min_size=2, max_size=3)

    assert len(results) > 0
    for graph6, spectrum, compute_seconds in results:
        assert 2 <= len(spectrum) <= 3


def test_query_by_contains(tmp_path):
    db_path = _build_order5_db(tmp_path)
    results = query.query_graphs(db_path, contains=2)

    assert len(results) > 0
    for graph6, spectrum, compute_seconds in results:
        assert 2 in spectrum


def test_query_by_not_contains(tmp_path):
    db_path = _build_order5_db(tmp_path)
    all_results = query.query_graphs(db_path)
    results = query.query_graphs(db_path, not_contains=2)

    assert len(results) < len(all_results)
    for graph6, spectrum, compute_seconds in results:
        assert 2 not in spectrum


def test_query_filters_combine_with_and(tmp_path):
    db_path = _build_order5_db(tmp_path)
    all_results = query.query_graphs(db_path)
    combined = query.query_graphs(db_path, min_size=1, contains=2)

    manual = [r for r in all_results if len(r[1]) >= 1 and 2 in r[1]]
    assert {r[0] for r in combined} == {r[0] for r in manual}
    assert len(combined) > 0


def test_query_sort_order(tmp_path):
    db_path = _build_order5_db(tmp_path)
    results = query.query_graphs(db_path, sort="compute_seconds", desc=True)

    times = [r[2] for r in results]
    assert times == sorted(times, reverse=True)


def test_query_raises_on_missing_db(tmp_path):
    missing = tmp_path / "does_not_exist.sqlite"

    try:
        query.query_graphs(missing)
        assert False, "expected an error for a missing database file"
    except FileNotFoundError:
        pass


def test_query_raises_clear_error_when_table_missing(tmp_path):
    db_path = tmp_path / "empty.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE unrelated (x INTEGER)")
    conn.commit()
    conn.close()

    try:
        query.query_graphs(db_path)
        assert False, "expected a clear error when graph_results table is missing"
    except RuntimeError as e:
        assert "record-details" in str(e) or "record_details" in str(e)


def test_query_empty_when_no_details_recorded(tmp_path):
    db_path = tmp_path / "order4.sqlite"
    driver.run(4, db_path)  # no record_details

    results = query.query_graphs(db_path)
    assert results == []


def test_cli_count_mode_ignores_limit(tmp_path):
    db_path = _build_order5_db(tmp_path)
    full_count = len(query.query_graphs(db_path))

    result = subprocess.run(
        [sys.executable, "py/query.py", str(db_path), "--count", "--limit", "1"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(full_count)


def test_cli_list_mode_respects_limit(tmp_path):
    db_path = _build_order5_db(tmp_path)
    result = subprocess.run(
        [sys.executable, "py/query.py", str(db_path), "--limit", "2"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 2


def test_cli_output_piped_to_head_does_not_crash(tmp_path):
    # Regression test: piping into `head` closes the read end early, which
    # used to surface as an ugly BrokenPipeError traceback on stderr.
    db_path = _build_order5_db(tmp_path)
    result = subprocess.run(
        f"{sys.executable} py/query.py {db_path} | head -1",
        shell=True,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert "BrokenPipeError" not in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_missing_db_gives_friendly_error(tmp_path):
    missing = tmp_path / "nope.sqlite"
    result = subprocess.run(
        [sys.executable, "py/query.py", str(missing)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "no such" in combined or "not found" in combined
