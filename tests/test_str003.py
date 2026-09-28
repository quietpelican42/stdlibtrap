from pathlib import Path

from stdlibtrap.checker import check_source

FIXTURES = Path(__file__).parent / "fixtures"


def test_positive_fixture_flags_every_undrained_pipe() -> None:
    source = (FIXTURES / "str003_positive.py").read_text()
    findings = check_source(source, select={"STR003"})
    codes = {f.code for f in findings}
    assert codes == {"STR003"}
    assert len(findings) == 6


def test_negative_fixture_is_quiet() -> None:
    source = (FIXTURES / "str003_negative.py").read_text()
    findings = check_source(source, select={"STR003"})
    assert findings == []


def test_message_quotes_the_docs_and_names_the_fix() -> None:
    source = (
        "import subprocess\n\n"
        "def f():\n"
        "    p = subprocess.Popen(['x'], stdout=subprocess.PIPE)\n"
        "    p.wait()\n"
    )
    findings = check_source(source, select={"STR003"})
    assert len(findings) == 1
    message = findings[0].message
    assert "communicate()" in message
    assert (
        "This will deadlock when using stdout=PIPE or stderr=PIPE and the "
        "child process generates enough output to a pipe such that it "
        "blocks waiting for the OS pipe buffer to accept more data."
    ) in message
