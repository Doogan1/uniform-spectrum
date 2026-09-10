"""
Compatibility shim for pytest's internal py module.

This package is named 'py', which collides with a compatibility shim that pytest
ships internally for the legacy 'pylib' package. At pytest startup, _pytest/compat.py
executes `import py; py.path.local`, which will import our local py package.

To avoid AttributeError when pytest tries to access py.path or py.error, we
populate sys.modules["py.path"] and sys.modules["py.error"] with the shim's
implementations that pytest expects.

This side effect is intentionally unconditional and global — it fires whenever
anything imports the py package (not just when pytest is running), as long as
pytest is installed in the environment. This is safe for this project because:

1. The py package is only intended to be imported by test code (py.generate)
2. The sys.modules side effect is transparent to callers (no attribute access)
3. It's the same workaround that pytest's own py.py shim uses

If pytest is installed but _pytest._py is unavailable or malformed (e.g. from
a future pytest version where these internals are removed), we emit a warning
instead of failing silently, so the error will be traceable.
"""

import sys
import warnings

try:
    import _pytest._py.error as error
    import _pytest._py.path as path
except ImportError:
    # _pytest itself is not importable; pytest is not installed in this environment.
    # Skip the shim — the py package will work fine for its own usage (py.generate),
    # and pytest won't be present to complain about missing py.path/py.error.
    pass
except (AttributeError, ImportError) as e:
    # _pytest is importable, but _pytest._py.error or _pytest._py.path is missing or
    # malformed (e.g. removed in a future pytest version). This is a sign that pytest's
    # internals have changed in a way that breaks our shim.
    warnings.warn(
        f"pytest compatibility shim in py/__init__.py failed to load _pytest._py modules: {e}. "
        "py.path and py.error will not be available, and pytest may fail at startup.",
        RuntimeWarning,
        stacklevel=2,
    )
else:
    # _pytest._py modules loaded successfully; register them in sys.modules so pytest
    # can find them under the py namespace.
    sys.modules["py.error"] = error
    sys.modules["py.path"] = path
