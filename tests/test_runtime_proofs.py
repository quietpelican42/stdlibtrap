"""Each positive pattern actually executed, proving the trap is real (not just
a hypothetical the static checker guesses at).
"""

from __future__ import annotations

import asyncio
import functools
import subprocess
import sys
import time

import pytest


def test_str001_runtime_proof_second_call_raises() -> None:
    @functools.lru_cache
    async def cached(x: int) -> int:
        return x * 2

    async def main() -> None:
        first = await cached(1)
        assert first == 2
        with pytest.raises(RuntimeError, match="cannot reuse already awaited coroutine"):
            await cached(1)

    asyncio.run(main())


def test_str002_runtime_proof_specific_except_never_matches() -> None:
    async def boom() -> None:
        raise ValueError("bad")

    caught_value_error = False

    async def main() -> None:
        nonlocal caught_value_error
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(boom())
        except ValueError:
            caught_value_error = True

    with pytest.raises(ExceptionGroup) as exc_info:
        asyncio.run(main())

    assert caught_value_error is False
    assert isinstance(exc_info.value.exceptions[0], ValueError)


def test_str002_runtime_proof_except_exception_does_catch() -> None:
    # Confirms the noise-floor rule: except Exception is NOT a false negative
    # to fix, it genuinely catches the ExceptionGroup because ExceptionGroup
    # subclasses Exception.
    async def boom() -> None:
        raise ValueError("bad")

    caught = False

    async def main() -> None:
        nonlocal caught
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(boom())
        except Exception:
            caught = True

    asyncio.run(main())
    assert caught is True


def test_str003_runtime_proof_deadlocks_without_communicate() -> None:
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.write('x' * (2 * 1024 * 1024)); sys.stdout.flush()",
        ],
        stdout=subprocess.PIPE,
    )
    start = time.monotonic()
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            proc.wait(timeout=3)
    finally:
        elapsed = time.monotonic() - start
        proc.kill()
        proc.wait()
    assert elapsed >= 3


def test_str003_runtime_proof_communicate_avoids_deadlock() -> None:
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.write('x' * (2 * 1024 * 1024)); sys.stdout.flush()",
        ],
        stdout=subprocess.PIPE,
    )
    start = time.monotonic()
    stdout, _ = proc.communicate(timeout=10)
    elapsed = time.monotonic() - start
    assert len(stdout) == 2 * 1024 * 1024
    assert elapsed < 10
