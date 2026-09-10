# uniform-spectrum

Computing the uniform spectrum of graphs, and hunting for a counterexample
(or more evidence) for a conjecture: if `n-1` is in the uniform spectrum of
a graph of order `n`, is `n-2` always in it too?

See [`docs/superpowers/specs/2026-09-09-uniform-spectrum-design.md`](docs/superpowers/specs/2026-09-09-uniform-spectrum-design.md)
for the full design.

## Setup

```bash
sudo dnf install cmake gcc-c++ nauty   # geng, cmake, g++ (Fedora)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cmake -S core -B core/build -Dpybind11_DIR=$(python -m pybind11 --cmakedir)
cmake --build core/build
pytest
```
