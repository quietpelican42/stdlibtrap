"""AST-based detectors for three stdlib/asyncio traps.

Each rule resolves imports first (so ``import functools as ft`` or
``from functools import lru_cache as memo`` are recognised the same as the
un-aliased spelling), then walks the tree looking for the specific shape of
each trap. The detectors are deliberately conservative: when a construct
cannot be resolved confidently, the finding is skipped rather than guessed.
"""

from __future__ import annotations

import ast
import dataclasses
from collections.abc import Iterator

# ---------------------------------------------------------------------------
# Rule metadata
# ---------------------------------------------------------------------------

RULE_MESSAGES: dict[str, str] = {
    "STR001": (
        "'{name}' on an async function caches the coroutine object, not its "
        "result. The second call replays an already-awaited coroutine and "
        "raises RuntimeError: cannot reuse already awaited coroutine. Use "
        "the 'async-lru' package (or an explicit dict-based cache) instead."
    ),
    "STR002": (
        "'except {exc}' can never match here: asyncio.TaskGroup wraps every "
        "task failure in an ExceptionGroup, even when only one task raises. "
        "Use 'except* {exc}' instead."
    ),
    "STR003": (
        "Popen(...) opens a pipe (stdout=PIPE or stderr=PIPE) but is later "
        "{call}()ed without draining it. The subprocess docs warn: 'This "
        "will deadlock when using stdout=PIPE or stderr=PIPE and the child "
        "process generates enough output to a pipe such that it blocks "
        "waiting for the OS pipe buffer to accept more data. Use "
        "Popen.communicate() when using pipes to avoid that.' Use "
        "communicate() instead of {call}()."
    ),
}

ALL_RULES: tuple[str, ...] = tuple(sorted(RULE_MESSAGES))

_SUPPRESSION_PREFIX = "stdlibtrap: ignore["

_SAFE_EXCEPTION_NAMES = {
    "Exception",
    "BaseException",
    "ExceptionGroup",
    "BaseExceptionGroup",
    "builtins.Exception",
    "builtins.BaseException",
    "builtins.ExceptionGroup",
    "builtins.BaseExceptionGroup",
}

_CACHE_QUALNAMES = {"functools.lru_cache", "functools.cache"}


@dataclasses.dataclass(frozen=True)
class Diagnostic:
    """A single finding."""

    code: str
    line: int
    column: int
    message: str

    def format_text(self, filename: str) -> str:
        return f"{filename}:{self.line}:{self.column}: {self.code} {self.message}"


# ---------------------------------------------------------------------------
# Import resolution
# ---------------------------------------------------------------------------


class _ImportResolver:
    """Maps local names introduced by import statements to dotted qualnames."""

    def __init__(self, tree: ast.AST) -> None:
        # local name -> module dotted path, e.g. "ft" -> "functools"
        self.module_aliases: dict[str, str] = {}
        # local name -> "module.orig_name", e.g. "memo" -> "functools.lru_cache"
        self.from_aliases: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local = alias.asname or alias.name.split(".")[0]
                    self.module_aliases[local] = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                for alias in node.names:
                    local = alias.asname or alias.name
                    self.from_aliases[local] = f"{node.module}.{alias.name}"

    def resolve(self, expr: ast.expr) -> str | None:
        """Resolve a Name/Attribute chain to a canonical dotted qualname."""
        if isinstance(expr, ast.Name):
            if expr.id in self.from_aliases:
                return self.from_aliases[expr.id]
            if expr.id in self.module_aliases:
                return self.module_aliases[expr.id]
            return None
        if isinstance(expr, ast.Attribute):
            base = self.resolve(expr.value)
            if base is not None:
                return f"{base}.{expr.attr}"
            return None
        return None


def _decorator_target(dec: ast.expr) -> ast.expr:
    if isinstance(dec, ast.Call):
        return dec.func
    return dec


# ---------------------------------------------------------------------------
# STR001 — lru_cache/cache on an async def
# ---------------------------------------------------------------------------


def _check_str001(tree: ast.AST, resolver: _ImportResolver) -> Iterator[Diagnostic]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        for dec in node.decorator_list:
            target = _decorator_target(dec)
            qualname = resolver.resolve(target)
            if qualname in _CACHE_QUALNAMES:
                name = qualname.rsplit(".", 1)[-1]
                yield Diagnostic(
                    code="STR001",
                    line=dec.lineno,
                    column=dec.col_offset + 1,
                    message=RULE_MESSAGES["STR001"].format(name=name),
                )
                break  # one finding per function is enough


# ---------------------------------------------------------------------------
# STR002 — bare except after asyncio.TaskGroup
# ---------------------------------------------------------------------------


def _try_body_has_taskgroup(try_node: ast.Try, resolver: _ImportResolver) -> bool:
    for stmt in try_node.body:
        if not isinstance(stmt, ast.AsyncWith):
            continue
        for item in stmt.items:
            ctx = item.context_expr
            target = _decorator_target(ctx)
            if resolver.resolve(target) == "asyncio.TaskGroup":
                return True
    return False


def _handler_exception_names(handler: ast.ExceptHandler) -> list[str] | None:
    """Return the source spellings of the exception type(s), or None if bare."""
    if handler.type is None:
        return None
    if isinstance(handler.type, ast.Tuple):
        return [ast.unparse(elt) for elt in handler.type.elts]
    return [ast.unparse(handler.type)]


def _check_str002(tree: ast.AST, resolver: _ImportResolver) -> Iterator[Diagnostic]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        if not _try_body_has_taskgroup(node, resolver):
            continue
        for handler in node.handlers:
            names = _handler_exception_names(handler)
            if names is None:
                continue  # bare `except:` does catch ExceptionGroup
            if any(n in _SAFE_EXCEPTION_NAMES for n in names):
                continue  # Exception/BaseException/(Base)ExceptionGroup match
            exc_repr = ", ".join(names) if len(names) > 1 else names[0]
            yield Diagnostic(
                code="STR002",
                line=handler.lineno,
                column=handler.col_offset + 1,
                message=RULE_MESSAGES["STR002"].format(exc=exc_repr),
            )


# ---------------------------------------------------------------------------
# STR003 — Popen(stdout/stderr=PIPE) waited on without communicate()
# ---------------------------------------------------------------------------

_FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def _iter_same_scope(node: ast.AST) -> Iterator[ast.AST]:
    """Yield descendants without crossing into a nested function/class scope."""
    stack: list[ast.AST] = list(ast.iter_child_nodes(node))
    while stack:
        current = stack.pop()
        yield current
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        stack.extend(ast.iter_child_nodes(current))


def _popen_piped_streams(
    call: ast.Call, resolver: _ImportResolver
) -> set[str] | None:
    if resolver.resolve(call.func) != "subprocess.Popen":
        return None
    piped: set[str] = set()
    for kw in call.keywords:
        if kw.arg in ("stdout", "stderr") and resolver.resolve(kw.value) == "subprocess.PIPE":
            piped.add(kw.arg)
    return piped or None


def _check_str003_function(
    fn: _FunctionNode, resolver: _ImportResolver
) -> Iterator[Diagnostic]:
    # var name -> (Popen() call node, piped stream names)
    popen_vars: dict[str, tuple[ast.Call, set[str]]] = {}
    communicated: set[str] = set()
    read_pipes: set[str] = set()
    wait_calls: list[tuple[str, str, ast.Call]] = []
    poll_loop_calls: list[tuple[str, str, ast.Call]] = []

    for node in _iter_same_scope(fn):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            piped = _popen_piped_streams(node.value, resolver)
            if piped is not None:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        popen_vars[target.id] = (node.value, piped)

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            base = node.func.value
            if isinstance(base, ast.Name):
                if attr == "communicate":
                    communicated.add(base.id)
                elif attr == "wait":
                    wait_calls.append((base.id, attr, node))
            if (
                isinstance(base, ast.Attribute)
                and base.attr in ("stdout", "stderr")
                and isinstance(base.value, ast.Name)
                and attr in ("read", "readline", "readlines")
            ):
                read_pipes.add(base.value.id)

        if isinstance(node, ast.For):
            it = node.iter
            if (
                isinstance(it, ast.Attribute)
                and it.attr in ("stdout", "stderr")
                and isinstance(it.value, ast.Name)
            ):
                read_pipes.add(it.value.id)

        if isinstance(node, ast.While):
            for sub in ast.walk(node):
                if (
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "poll"
                    and isinstance(sub.func.value, ast.Name)
                ):
                    poll_loop_calls.append((sub.func.value.id, "poll", sub))

    reported: set[str] = set()
    for varname, call_attr, call_node in (*wait_calls, *poll_loop_calls):
        if varname in reported:
            continue
        if varname not in popen_vars:
            continue
        if varname in communicated or varname in read_pipes:
            continue
        reported.add(varname)
        popen_call, piped = popen_vars[varname]
        streams = " and ".join(sorted(piped))
        yield Diagnostic(
            code="STR003",
            line=call_node.lineno,
            column=call_node.col_offset + 1,
            message=(
                f"'{varname}' from Popen(...) at line {popen_call.lineno} pipes "
                f"{streams} but is never drained. "
            )
            + RULE_MESSAGES["STR003"].format(call=call_attr),
        )


def _check_str003(tree: ast.AST, resolver: _ImportResolver) -> Iterator[Diagnostic]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield from _check_str003_function(node, resolver)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

_CHECKS = {
    "STR001": _check_str001,
    "STR002": _check_str002,
    "STR003": _check_str003,
}


def check_tree(
    tree: ast.AST,
    *,
    select: set[str] | None = None,
    ignore: set[str] | None = None,
) -> list[Diagnostic]:
    """Run the enabled checks against an already-parsed module."""
    resolver = _ImportResolver(tree)
    codes = set(select) if select is not None else set(ALL_RULES)
    if ignore:
        codes -= set(ignore)
    findings: list[Diagnostic] = []
    for code in sorted(codes):
        check = _CHECKS.get(code)
        if check is None:
            continue
        findings.extend(check(tree, resolver))
    findings.sort(key=lambda d: (d.line, d.column, d.code))
    return findings


def check_source(
    source: str,
    *,
    filename: str = "<string>",
    select: set[str] | None = None,
    ignore: set[str] | None = None,
) -> list[Diagnostic]:
    """Parse ``source`` and run the enabled checks, applying suppression comments."""
    tree = ast.parse(source, filename=filename)
    findings = check_tree(tree, select=select, ignore=ignore)
    return _apply_suppressions(source, findings)


def _suppressed_codes(line_text: str) -> set[str]:
    idx = line_text.find(_SUPPRESSION_PREFIX)
    if idx == -1:
        return set()
    rest = line_text[idx + len(_SUPPRESSION_PREFIX) :]
    end = rest.find("]")
    if end == -1:
        return set()
    codes = rest[:end]
    return {c.strip() for c in codes.split(",") if c.strip()}


def _apply_suppressions(source: str, findings: list[Diagnostic]) -> list[Diagnostic]:
    if not findings:
        return findings
    lines = source.splitlines()
    kept: list[Diagnostic] = []
    for diag in findings:
        if 1 <= diag.line <= len(lines):
            line_text = lines[diag.line - 1]
            if diag.code in _suppressed_codes(line_text):
                continue
        kept.append(diag)
    return kept
