# tests/test_visualize.py
import subprocess
import sys
from pathlib import Path

import networkx as nx

from py import visualize

REPO_ROOT = Path(__file__).resolve().parent.parent


def _example_graph6():
    G = nx.cycle_graph(4)
    return nx.to_graph6_bytes(G, header=False).decode().strip()


def test_safe_filename_has_no_path_separators_and_right_extension():
    graph6 = _example_graph6()
    name = visualize.safe_filename(graph6, "png")
    assert "/" not in name
    assert name.endswith(".png")


def test_safe_filename_is_distinct_for_distinct_graphs():
    a = visualize.safe_filename("Cl", "png")
    b = visualize.safe_filename("C~", "png")
    assert a != b


def test_draw_graph_returns_axes_with_graph6_and_spectrum_in_title():
    graph6 = _example_graph6()  # C4 -- established elsewhere in this project to have an empty spectrum
    ax = visualize.draw_graph(graph6)
    title = ax.get_title()
    assert graph6 in title
    assert "[]" in title

    import matplotlib.pyplot as plt

    plt.close(ax.figure)


def test_cli_saves_single_graph_to_file(tmp_path):
    graph6 = _example_graph6()
    out_path = tmp_path / "graph.png"
    result = subprocess.run(
        [sys.executable, "py/visualize.py", graph6, "--out", str(out_path)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_cli_stdin_batch_mode_saves_one_file_per_line(tmp_path):
    graph6_a = _example_graph6()
    graph6_b = nx.to_graph6_bytes(nx.complete_graph(4), header=False).decode().strip()
    stdin_input = f"{graph6_a}\t[]\t0.000001\n{graph6_b}\t[1, 2, 3]\t0.000001\n"

    outdir = tmp_path / "figs"
    result = subprocess.run(
        [sys.executable, "py/visualize.py", "--stdin", "--outdir", str(outdir)],
        input=stdin_input,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr
    saved = list(outdir.glob("*.png"))
    assert len(saved) == 2


def test_cli_stdin_without_outdir_gives_clear_error():
    result = subprocess.run(
        [sys.executable, "py/visualize.py", "--stdin"],
        input="Cl\n",
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode != 0
    assert "outdir" in result.stderr.lower()


def test_cli_no_graph6_and_no_stdin_gives_clear_error():
    result = subprocess.run(
        [sys.executable, "py/visualize.py"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode != 0
    combined = result.stderr.lower()
    assert "graph6" in combined or "stdin" in combined


def test_end_to_end_query_piped_into_visualize(tmp_path):
    from py import driver

    db_path = tmp_path / "order5.sqlite"
    driver.run(5, db_path, record_details=True)

    outdir = tmp_path / "figs"
    query_proc = subprocess.run(
        [sys.executable, "py/query.py", str(db_path), "--spectrum-size", "1"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert query_proc.returncode == 0, query_proc.stderr

    viz_proc = subprocess.run(
        [sys.executable, "py/visualize.py", "--stdin", "--outdir", str(outdir)],
        input=query_proc.stdout,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert viz_proc.returncode == 0, viz_proc.stderr
    saved = list(outdir.glob("*.png"))
    # Order 5 has exactly 2 singleton-spectrum graphs (established while building query.py).
    assert len(saved) == 2
