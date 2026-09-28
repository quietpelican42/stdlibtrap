"""Positive cases for STR001: lru_cache/cache on an async def."""

import functools
import functools as ft
from functools import cache, lru_cache
from functools import lru_cache as memo


@functools.lru_cache
async def plain_attribute(x: int) -> int:
    return x


@functools.lru_cache(maxsize=32)
async def attribute_call(x: int) -> int:
    return x


@functools.cache
async def attribute_cache(x: int) -> int:
    return x


@ft.lru_cache
async def aliased_module(x: int) -> int:
    return x


@lru_cache
async def from_import(x: int) -> int:
    return x


@lru_cache()
async def from_import_call(x: int) -> int:
    return x


@cache
async def from_import_cache(x: int) -> int:
    return x


@memo
async def aliased_from_import(x: int) -> int:
    return x


class Service:
    @functools.lru_cache
    async def method(self, x: int) -> int:
        return x

    @staticmethod
    @cache
    async def static_method(x: int) -> int:
        return x
