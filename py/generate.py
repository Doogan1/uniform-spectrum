"""Streams non-isomorphic graphs of a given order using nauty's geng."""

import shutil
import subprocess
from typing import Iterator

GENG_CANDIDATES = ["geng", "nauty-geng"]


def _find_geng() -> str:
    for name in GENG_CANDIDATES:
        if shutil.which(name):
            return name
    raise RuntimeError(
        "Could not find a `geng` binary (tried: "
        + ", ".join(GENG_CANDIDATES)
        + "). Install nauty (e.g. `sudo dnf install nauty` on Fedora, "
        "or build from https://pallini.di.uniroma1.it/) and ensure "
        "its geng binary is on PATH."
    )


def run_geng(n: int) -> Iterator[str]:
    """Yield one graph6 string per non-isomorphic graph of order n."""
    binary = _find_geng()
    proc = subprocess.Popen(
        [binary, str(n)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            line = line.strip()
            if line:
                yield line
    finally:
        proc.stdout.close()
        returncode = proc.wait()
        if returncode != 0:
            raise RuntimeError(f"geng exited with code {returncode}")
