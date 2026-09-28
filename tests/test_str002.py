from pathlib import Path

from stdlibtrap.checker import check_source

FIXTURES = Path(__file__).parent / "fixtures"


def test_positive_fixture_flags_every_unmatchable_handler() -> None:
    source = (FIXTURES / "str002_positive.py").read_text()
    findings = check_source(source, select={"STR002"})
    codes = {f.code for f in findings}
    assert codes == {"STR002"}
    # single(1) + multiple(2) + tuple(1) + aliased module(1) + aliased from-import(1)
    assert len(findings) == 6


def test_negative_fixture_is_quiet() -> None:
    source = (FIXTURES / "str002_negative.py").read_text()
    findings = check_source(source, select={"STR002"})
    assert findings == []


def test_message_recommends_except_star() -> None:
    source = (
        "import asyncio\n\n"
        "async def boom():\n"
        "    raise ValueError\n\n"
        "async def f():\n"
        "    try:\n"
        "        async with asyncio.TaskGroup() as tg:\n"
        "            tg.create_task(boom())\n"
        "    except ValueError:\n"
        "        pass\n"
    )
    findings = check_source(source, select={"STR002"})
    assert len(findings) == 1
    assert "except* ValueError" in findings[0].message
