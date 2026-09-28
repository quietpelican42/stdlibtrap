"""Negative controls for STR002: except clauses that do (or can) match."""

import asyncio


async def boom() -> None:
    raise ValueError("bad")


async def catches_exception() -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(boom())
    except Exception:
        pass


async def catches_base_exception() -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(boom())
    except BaseException:
        pass


async def bare_except() -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(boom())
    except:  # noqa: E722
        pass


async def uses_except_star() -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(boom())
    except* ValueError:
        pass


async def tuple_includes_exception() -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(boom())
    except (ValueError, Exception):
        pass


async def no_taskgroup_at_all() -> None:
    try:
        raise ValueError("bad")
    except ValueError:
        pass


async def taskgroup_not_in_try() -> None:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(boom())
    try:
        raise ValueError("unrelated")
    except ValueError:
        pass
