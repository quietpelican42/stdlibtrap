"""Command-line entry point for stdlibtrap."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path

from stdlibtrap.checker import ALL_RULES, Diagnostic, check_source

_EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "build",
    "dist",
}


def _iter_python_files(paths: Sequence[str]) -> Iterator[Path]:
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            yield path
            continue
        if path.is_dir():
            for candidate in sorted(path.rglob("*.py")):
                if any(part in _EXCLUDED_DIR_NAMES for part in candidate.parts):
                    continue
                yield candidate
            continue
        raise FileNotFoundError(raw)


def _parse_code_list(value: str | None) -> set[str] | None:
    if value is None:
        return None
    codes = {c.strip() for c in value.split(",") if c.strip()}
    unknown = codes - set(ALL_RULES)
    if unknown:
        raise ValueError(f"unknown rule code(s): {', '.join(sorted(unknown))}")
    return codes


def _format_text(filename: str, diagnostics: list[Diagnostic]) -> list[str]:
    return [d.format_text(filename) for d in diagnostics]


def _format_github(filename: str, diagnostics: list[Diagnostic]) -> list[str]:
    lines = []
    for d in diagnostics:
        lines.append(
            f"::error file={filename},line={d.line},col={d.column},"
            f"title={d.code}::{d.message}"
        )
    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stdlibtrap",
        description=(
            "Flag stdlib/asyncio traps that mainstream linters do not catch: "
            "lru_cache on async def, plain except after asyncio.TaskGroup, "
            "and subprocess.Popen pipe deadlocks."
        ),
    )
    parser.add_argument("paths", nargs="*", default=["."], help="files or directories to check")
    parser.add_argument(
        "--select",
        default=None,
        help=f"comma-separated rule codes to run (default: all of {', '.join(ALL_RULES)})",
    )
    parser.add_argument(
        "--ignore",
        default=None,
        help="comma-separated rule codes to skip",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "github"],
        default="text",
        help="output format (default: text)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        select = _parse_code_list(args.select)
        ignore = _parse_code_list(args.ignore)
    except ValueError as exc:
        print(f"stdlibtrap: {exc}", file=sys.stderr)
        return 2

    try:
        files = list(_iter_python_files(args.paths))
    except FileNotFoundError as exc:
        print(f"stdlibtrap: path not found: {exc}", file=sys.stderr)
        return 2

    all_diagnostics: list[tuple[str, Diagnostic]] = []
    had_error = False
    for file_path in files:
        try:
            source = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"stdlibtrap: could not read {file_path}: {exc}", file=sys.stderr)
            had_error = True
            continue
        try:
            diagnostics = check_source(source, filename=str(file_path), select=select, ignore=ignore)
        except SyntaxError as exc:
            print(f"stdlibtrap: could not parse {file_path}: {exc}", file=sys.stderr)
            had_error = True
            continue
        for diag in diagnostics:
            all_diagnostics.append((str(file_path), diag))

    if args.format == "json":
        payload = [
            {
                "file": fname,
                "code": d.code,
                "line": d.line,
                "column": d.column,
                "message": d.message,
            }
            for fname, d in all_diagnostics
        ]
        print(json.dumps(payload, indent=2))
    elif args.format == "github":
        for fname, d in all_diagnostics:
            print(_format_github(fname, [d])[0])
    else:
        for fname, d in all_diagnostics:
            print(d.format_text(fname))

    if had_error:
        return 2
    if all_diagnostics:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
