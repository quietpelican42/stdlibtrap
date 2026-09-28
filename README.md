# stdlibtrap

A linter for three stdlib/asyncio bugs that read as correct code and pass ruff, pylint, flake8-async, and bandit unflagged.

```sh
$ stdlibtrap src/
src/app.py:6:2: STR001 'lru_cache' on an async function caches the coroutine object, not its result. The second call replays an already-awaited coroutine and raises RuntimeError: cannot reuse already awaited coroutine. Use the 'async-lru' package (or an explicit dict-based cache) instead.
src/app.py:16:5: STR002 'except ValueError' can never match here: asyncio.TaskGroup wraps every task failure in an ExceptionGroup, even when only one task raises. Use 'except* ValueError' instead.
src/app.py:22:5: STR003 'proc' from Popen(...) at line 21 pipes stdout but is never drained. Popen(...) opens a pipe (stdout=PIPE or stderr=PIPE) but is later wait()ed without draining it. The subprocess docs warn: 'This will deadlock when using stdout=PIPE or stderr=PIPE and the child process generates enough output to a pipe such that it blocks waiting for the OS pipe buffer to accept more data. Use Popen.communicate() when using pipes to avoid that.' Use communicate() instead of wait().
$ echo $?
1
```

## Why

Each of these three constructs type-checks, runs, and looks idiomatic. They fail only under conditions the author's test run didn't hit — a second call, a task that actually raises, output that crosses a buffer size.

- `@functools.lru_cache` on an `async def` caches the coroutine object the first call returns, not its result. The second call awaits an already-completed coroutine and raises `RuntimeError: cannot reuse already awaited coroutine`.
- A `try/except SomeError` wrapped around `async with asyncio.TaskGroup()` never matches, because `TaskGroup` always raises an `ExceptionGroup`, even when exactly one task fails. The handler silently does nothing; the original exception is unhandled.
- `subprocess.Popen(..., stdout=PIPE)` followed by `.wait()` (or a `.poll()` loop) without `.communicate()` deadlocks once the child writes more than the OS pipe buffer holds (64 KiB on Linux, similar elsewhere). The subprocess docs warn about this directly: "This will deadlock when using stdout=PIPE or stderr=PIPE and the child process generates enough output to a pipe such that it blocks waiting for the OS pipe buffer to accept more data. Use `Popen.communicate()` when using pipes to avoid that." — but nothing enforces it.

Checked before building: ruff's full rule set (969 rules as of this writing), flake8-async's ~60 `ASYNC` rules, pylint, and bandit. None of them cover any of these three shapes. The closest neighbors catch different problems — ruff's `B019` is about `lru_cache` retaining `self`, flake8-async's `ASYNC220` is about calling `subprocess.Popen` synchronously *inside* an async function (blocking the event loop, not a pipe deadlock), and pylint's `W1509`/bandit's `B602` are about `preexec_fn`/`shell=True`, not pipe draining.

Measured: `python examples/scan_stdlib.py`, scanning the CPython 3.14.7 `Lib/` tree that ships with the interpreter running it (1868 `.py` files):

```
1868 .py files scanned, 5 could not be read/parsed
findings: {'STR003': 8}
```

The 5 unreadable files are CPython's own tokenizer test fixtures (`test/tokenizedata/badsyntax_*.py`, legacy-encoded modules) — deliberately invalid, and `stdlibtrap` exits 2 (could-not-analyse) on them rather than guessing. All 8 findings are `STR003`, all inside `test/test_subprocess.py`, `test/test_os.py`, and `ctypes/_aix.py`. Zero `STR001`/`STR002` findings anywhere in the stdlib.

Running the same build over four popular pure-Python projects (`requests`, `black`, `httpx`, `pip`, cloned locally, 1116 more `.py` files) found one more `STR003` hit, in `pip/_vendor/distlib/util.py`, and nothing else.

Classifying all 9 real-world `STR003` findings by hand:

- **7 true positives by the rule's own definition** — the function creates a `Popen` with a piped stream, later calls `.wait()`, and never calls `.communicate()` or reads the pipe in that function. Whether *this* run deadlocks depends on how much the child writes, which is a runtime property the source doesn't guarantee; CPython's test fixtures keep output to a few bytes on purpose, so none currently hang. The pattern is still the one the subprocess docs warn about.
- **2 false positives**, both from the same root cause: the pipe genuinely is drained, but through a level of indirection this intra-function checker doesn't follow — `ctypes/_aix.py` drains `p.stdout` inside a helper function called from a `while` loop, and `pip/_vendor/distlib/util.py` drains both pipes on background `threading.Thread` targets. Both are documented under Limitations.

## Installation

```sh
pip install stdlibtrap
```

Zero runtime dependencies — the checks are built on `ast` from the standard library. Python 3.11+.

## Usage

### Check a project

```sh
stdlibtrap src/ tests/
```

Exits `0` with no output if clean, `1` if it found something, `2` if a file couldn't be read or parsed (and says which, on stderr).

### Run a single rule

```sh
stdlibtrap --select STR003 .
```

### Run as a module

```sh
python -m stdlibtrap .
```

### Suppress one finding

```python
@functools.lru_cache  # stdlibtrap: ignore[STR001]
async def cached_lookup(key: str) -> Result:
    ...
```

### Wire into CI

```sh
stdlibtrap --format github src/ >> "$GITHUB_STEP_SUMMARY" || true
stdlibtrap src/  # non-zero exit fails the job on real findings
```

## Reference

### CLI

| Flag | Default | Description |
| --- | --- | --- |
| `paths` | `.` | Files or directories to check (directories are walked recursively, skipping `.git`, `.venv`, `__pycache__`, `node_modules`, `build`, `dist`). |
| `--select CODES` | all rules | Comma-separated rule codes to run. |
| `--ignore CODES` | none | Comma-separated rule codes to skip. |
| `--format {text,json,github}` | `text` | Output format. `github` emits `::error` workflow commands. |

Exit codes: `0` no findings, `1` findings reported, `2` a path was missing or a file could not be read/parsed (details on stderr).

### Rules

| Code | Flags | Fix |
| --- | --- | --- |
| `STR001` | `@functools.lru_cache` / `@functools.cache` (any import spelling or alias) decorating an `async def`, function or method. | Use the `async-lru` package, or cache manually with a `dict` keyed on the arguments. |
| `STR002` | A `try:` whose body opens `async with asyncio.TaskGroup()` (any import spelling or alias), followed by `except SomeSpecificError:` where `SomeSpecificError` isn't `Exception`/`BaseException`/`ExceptionGroup`/`BaseExceptionGroup`. | Use `except* SomeSpecificError:`. |
| `STR003` | `subprocess.Popen(..., stdout=PIPE)` and/or `stderr=PIPE` (any import spelling), whose result is later `.wait()`ed, or `.poll()`ed inside a `while` loop, in the same function, without a `.communicate()` call or a read/iteration of the piped stream(s) in that function. | Use `Popen.communicate()`, or read the pipe(s) as they're produced. |

### Per-line suppression

`# stdlibtrap: ignore[STR001]` on the reported line skips that finding. `# stdlibtrap: ignore[STR001,STR002]` skips more than one code on the same line.

## How it works

`stdlibtrap` parses each file with `ast`, resolves `import`/`from...import` aliases into canonical dotted names (so `import functools as ft` and `from functools import lru_cache as memo` are recognized the same as the unaliased spelling), then walks the tree per rule:

- `STR001` looks at every `async def`'s decorator list for a resolved `functools.lru_cache`/`functools.cache`.
- `STR002` looks at every plain `try` (not `try*`) whose body contains a top-level `async with` opening `asyncio.TaskGroup()`, and checks each `except` clause's exception type(s) against the small set that can actually match an `ExceptionGroup`.
- `STR003` walks each function's own statements (not nested function/class bodies) tracking `Popen(...)` assignments with a piped `stdout`/`stderr`, then checks whether `.wait()`/looped `.poll()` on that variable is preceded by `.communicate()` or a direct read of the piped stream, within the same function.

## Limitations

- `STR003` is intra-function only, by design (see `PYTHON_SPEC.md`/build notes) — it does not follow the pipe into a helper function or a thread target. This produces false positives on code that drains the pipe indirectly (see the `ctypes/_aix.py` and `pip` examples measured above). It also does not track aliasing (`f = proc.stdout; f.read()` is not recognized as a read of `proc.stdout`).
- `STR002` only handles a `try` body whose `async with asyncio.TaskGroup()` appears directly at the top level of the `try` block, matching the spec's scope. A `TaskGroup` opened conditionally, or several statements deep, is not checked.
- None of the three rules attempt cross-file or cross-function data flow. Each is a single-file, mostly single-function, syntactic check.
- No autofix. The message names the fix; applying it is manual.
- `except*` syntax is Python 3.11+; parsing a file that mixes `except` and `except*` on the same `try` is a `SyntaxError` in the source itself, not something `stdlibtrap` needs to handle.

## Compatibility

Built and run on Python 3.14.7 (macOS/arm64) only. CI (not yet run) targets 3.11, 3.12, 3.13, and 3.14 on Linux via `.github/workflows/test.yml`; those entries are untested by this author, not verified.

## Development

```sh
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/python -m mypy src --strict
```

## License

MIT. See [LICENSE](LICENSE).
