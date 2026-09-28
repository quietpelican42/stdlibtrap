"""stdlibtrap: a linter for stdlib/asyncio traps mainstream linters miss."""

from stdlibtrap.checker import Diagnostic, check_source, check_tree

__version__ = "0.1.0"

__all__ = ["Diagnostic", "check_source", "check_tree", "__version__"]
