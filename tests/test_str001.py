from pathlib import Path

from stdlibtrap.checker import check_source

FIXTURES = Path(__file__).parent / "fixtures"


def test_positive_fixture_flags_every_case() -> None:
    source = (FIXTURES / "str001_positive.py").read_text()
    findings = check_source(source, select={"STR001"})
    codes = {f.code for f in findings}
    assert codes == {"STR001"}
    # 8 module-level cases + method + static method = 10
    assert len(findings) == 10


def test_negative_fixture_is_quiet() -> None:
    source = (FIXTURES / "str001_negative.py").read_text()
    findings = check_source(source, select={"STR001"})
    assert findings == []


def test_message_names_the_fix() -> None:
    source = (
        "import functools\n\n"
        "@functools.lru_cache\n"
        "async def f(x):\n"
        "    return x\n"
    )
    findings = check_source(source, select={"STR001"})
    assert len(findings) == 1
    assert "async-lru" in findings[0].message
    assert "RuntimeError" in findings[0].message
