"""Checks the conjecture: if n-1 is in a graph's uniform spectrum, n-2 must be too."""


def check(n: int, spectrum: set) -> bool | None:
    if n < 3:
        return None
    if (n - 1) in spectrum:
        return (n - 2) in spectrum
    return True
