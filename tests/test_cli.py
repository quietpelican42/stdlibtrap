import json
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "stdlibtrap", *args],
        capture_output=True,
        text=True,
    )


def test_clean_file_exits_zero(tmp_path: Path) -> None:
    clean = tmp_path / "clean.py"
    clean.write_text("def f(x):\n    return x\n")
    result = run_cli([str(clean)])
    assert result.returncode == 0
    assert result.stdout == ""


def test_findings_exit_one_text_format() -> None:
    result = run_cli([str(FIXTURES / "str001_positive.py")])
    assert result.returncode == 1
    assert "STR001" in result.stdout


def test_missing_path_exits_two() -> None:
    result = run_cli(["/nonexistent/path/that/does/not/exist.py"])
    assert result.returncode == 2


def test_syntax_error_exits_two(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("def f(:\n")
    result = run_cli([str(bad)])
    assert result.returncode == 2


def test_json_format(tmp_path: Path) -> None:
    result = run_cli(["--format", "json", str(FIXTURES / "str003_positive.py")])
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert all(item["code"] == "STR003" for item in payload)
    assert len(payload) == 6


def test_github_format() -> None:
    result = run_cli(["--format", "github", str(FIXTURES / "str002_positive.py")])
    assert result.returncode == 1
    assert result.stdout.startswith("::error ")


def test_select_limits_to_one_rule() -> None:
    result = run_cli(
        [
            "--select",
            "STR001",
            str(FIXTURES / "str001_positive.py"),
            str(FIXTURES / "str002_positive.py"),
        ]
    )
    assert result.returncode == 1
    assert "STR002" not in result.stdout
    assert "STR001" in result.stdout


def test_ignore_excludes_a_rule() -> None:
    result = run_cli(["--ignore", "STR001", str(FIXTURES / "str001_positive.py")])
    assert result.returncode == 0
    assert result.stdout == ""


def test_unknown_select_code_exits_two() -> None:
    result = run_cli(["--select", "STR999", str(FIXTURES / "str001_positive.py")])
    assert result.returncode == 2


def test_directory_argument_walks_python_files(tmp_path: Path) -> None:
    (tmp_path / "clean.py").write_text("def f(x):\n    return x\n")
    (tmp_path / "sub").mkdir()
    positive_source = (FIXTURES / "str001_positive.py").read_text()
    (tmp_path / "sub" / "bad.py").write_text(positive_source)
    result = run_cli([str(tmp_path)])
    assert result.returncode == 1
    assert "STR001" in result.stdout
