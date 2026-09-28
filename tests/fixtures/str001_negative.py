"""Negative controls for STR001: caching that is fine."""

import functools
from functools import lru_cache


@functools.lru_cache
def sync_function(x: int) -> int:
    return x


@lru_cache(maxsize=16)
def sync_with_args(x: int) -> int:
    return x


async def uncached_async(x: int) -> int:
    return x


def other_decorator_factory(fn: object) -> object:
    return fn


@other_decorator_factory
async def decorated_but_not_cached(x: int) -> int:
    return x


class Service:
    @functools.lru_cache
    def sync_method(self, x: int) -> int:
        return x
