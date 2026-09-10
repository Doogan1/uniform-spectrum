# Compatibility with pytest's py module shim
# These imports allow our local py package to coexist with pytest's expectations
try:
    import _pytest._py.error as error
    import _pytest._py.path as path

    import sys
    sys.modules["py.error"] = error
    sys.modules["py.path"] = path
except ImportError:
    # If pytest is not available, skip these imports
    pass
