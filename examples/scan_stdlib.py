"""Run stdlibtrap over the local CPython stdlib and report what it finds.

No network access needed: this uses the ``Lib/`` tree that ships with the
interpreter running this script (located via ``sysconfig``), which is already
on disk. Run with:

    python examples/scan_stdlib.py
"""

from __future__ import annotations

import sysconfig
from collections import Counter
from pathlib import Path

from stdlibtrap.cli import _iter_python_files
from stdlibtrap.checker import check_source


def main() -> None:
    stdlib = Path(sysconfig.get_paths()["stdlib"])
    print(f"Scanning {stdlib}")

    files = 0
    parse_errors = 0
    counts: Counter[str] = Counter()

    for path in _iter_python_files([str(stdlib)]):
        files += 1
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            parse_errors += 1
            continue
        try:
            findings = check_source(source, filename=str(path))
        except SyntaxError:
            parse_errors += 1
            continue
        for finding in findings:
            counts[finding.code] += 1
            print(f"  {path.relative_to(stdlib)}:{finding.line}: {finding.code}")

    print(f"\n{files} .py files scanned, {parse_errors} could not be read/parsed")
    print(f"findings: {dict(counts)}")


if __name__ == "__main__":
    main()
