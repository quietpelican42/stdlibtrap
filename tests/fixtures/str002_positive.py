"""Positive cases for STR002: except after asyncio.TaskGroup that can never match."""

import asyncio
import asyncio as aio
from asyncio import TaskGroup


async def boom() -> None:
    raise ValueError("bad")


async def single_specific_handler() -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(boom())
    except ValueError:
        pass


async def multiple_handlers() -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(boom())
    except ValueError:
        pass
    except TypeError:
        pass


async def tuple_handler() -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(boom())
    except (ValueError, TypeError):
        pass


async def aliased_module() -> None:
    try:
        async with aio.TaskGroup() as tg:
            tg.create_task(boom())
    except ValueError:
        pass


async def aliased_from_import() -> None:
    try:
        async with TaskGroup() as tg:
            tg.create_task(boom())
    except ValueError:
        pass
