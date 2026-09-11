# py/visualize.py
"""Render a graph (from its graph6 encoding) using networkx + matplotlib."""

import sys
from pathlib import Path
from urllib.parse import quote

import networkx as nx

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "core" / "build"))
import uniform_spectrum_core as core  # noqa: E402


def safe_filename(graph6: str, ext: str) -> str:
    """A filesystem-safe filename derived from a graph6 string (graph6 can
    contain characters like `?`, `~`, `{`, `}`, `\\` that are awkward in
    filenames)."""
    return f"{quote(graph6, safe='')}.{ext}"


def draw_graph(graph6: str, spectrum=None, ax=None):
    """Draw a graph on the given (or a new) matplotlib Axes, titled with its
    graph6 encoding and uniform spectrum. Returns the Axes."""
    import matplotlib.pyplot as plt

    G = nx.from_graph6_bytes(graph6.encode())
    if spectrum is None:
        spectrum = sorted(core.spectrum_from_graph6(graph6))

    if ax is None:
        _, ax = plt.subplots()

    pos = nx.spring_layout(G, seed=0)
    nx.draw(G, pos, ax=ax, with_labels=True, node_color="lightblue", node_size=500)
    ax.set_title(f"{graph6}\nspectrum: {spectrum}")
    return ax


def _save(graph6: str, outdir: Path, fmt: str) -> Path:
    import matplotlib.pyplot as plt

    ax = draw_graph(graph6)
    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / safe_filename(graph6, fmt)
    ax.figure.savefig(out_path)
    plt.close(ax.figure)
    return out_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Render a graph (or a batch of graphs) from graph6 encodings."
    )
    parser.add_argument("graph6", nargs="?", default=None, help="a single graph6 string to render")
    parser.add_argument(
        "--stdin",
        action="store_true",
        help=(
            "read one graph6 per line from stdin instead (accepts bare graph6 "
            "lines or query.py's tab-separated output -- only the first column "
            "is used)"
        ),
    )
    parser.add_argument("--out", type=str, default=None, help="save the single graph to this file")
    parser.add_argument(
        "--outdir", type=str, default=None, help="directory to save into (required with --stdin)"
    )
    parser.add_argument(
        "--format",
        choices=["png", "pdf", "svg"],
        default="png",
        help="image format for --outdir mode (default: png)",
    )
    args = parser.parse_args()

    if args.stdin and args.graph6 is not None:
        print("Error: pass either a graph6 argument or --stdin, not both.", file=sys.stderr)
        sys.exit(1)
    if not args.stdin and args.graph6 is None:
        print("Error: pass a graph6 string, or use --stdin to read several.", file=sys.stderr)
        sys.exit(1)
    if args.stdin and args.outdir is None:
        print("Error: --stdin requires --outdir (there's no single file to save to).", file=sys.stderr)
        sys.exit(1)

    saving = args.stdin or args.out is not None
    if saving:
        import matplotlib

        matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    if args.stdin:
        outdir = Path(args.outdir)
        count = 0
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            graph6 = line.split("\t")[0]
            out_path = _save(graph6, outdir, args.format)
            print(f"Saved {out_path}")
            count += 1
        print(f"Done. Saved {count} graph(s) to {outdir}")
    elif args.out is not None:
        out_path = Path(args.out)
        ax = draw_graph(args.graph6)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ax.figure.savefig(out_path)
        plt.close(ax.figure)
        print(f"Saved {out_path}")
    else:
        draw_graph(args.graph6)
        plt.show()
