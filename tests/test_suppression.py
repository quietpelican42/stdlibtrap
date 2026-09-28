from stdlibtrap.checker import check_source


def test_inline_suppression_drops_matching_code() -> None:
    source = (
        "import functools\n\n"
        "@functools.lru_cache  # stdlibtrap: ignore[STR001]\n"
        "async def f(x):\n"
        "    return x\n"
    )
    findings = check_source(source)
    assert findings == []


def test_inline_suppression_does_not_drop_other_codes() -> None:
    source = (
        "import functools\n\n"
        "@functools.lru_cache  # stdlibtrap: ignore[STR002]\n"
        "async def f(x):\n"
        "    return x\n"
    )
    findings = check_source(source)
    assert len(findings) == 1
    assert findings[0].code == "STR001"


def test_multiple_codes_in_one_suppression() -> None:
    source = (
        "import functools\n\n"
        "@functools.lru_cache  # stdlibtrap: ignore[STR001,STR002]\n"
        "async def f(x):\n"
        "    return x\n"
    )
    findings = check_source(source)
    assert findings == []
