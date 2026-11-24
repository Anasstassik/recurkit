import shlex
from pathlib import Path

import pytest

from tests.e2e.conftest import RunCli

CASES = Path(__file__).resolve().parent / "cases"
ARGS = sorted(CASES.glob("*.args"))


@pytest.mark.parametrize("args_file", ARGS, ids=[path.stem for path in ARGS])
def test_cli_case_prints_the_expected_output(run_cli: RunCli, args_file: Path) -> None:
    result = run_cli(*shlex.split(args_file.read_text("utf-8")))
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert result.stdout == args_file.with_suffix(".out").read_text("utf-8")


def test_every_case_has_arguments_and_expected_output() -> None:
    assert len(ARGS) >= 3
    for args_file in ARGS:
        assert args_file.with_suffix(".out").is_file()
    for ics in CASES.glob("*.ics"):
        assert any(ics.name in path.read_text("utf-8") for path in ARGS)


def test_process_reports_parse_errors_on_stderr(run_cli: RunCli, tmp_path: Path) -> None:
    broken = tmp_path / "broken.ics"
    broken.write_text(
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:x\nBEGIN:VEVENT\nUID:a\n"
        "DTSTART:20260101T090000\nDTEND:20260101T080000\nEND:VEVENT\nEND:VCALENDAR\n",
        "utf-8",
    )
    result = run_cli("expand", str(broken), "--from", "2026-01-01", "--to", "2026-01-31")
    assert result.returncode == 1
    assert result.stdout == ""
    assert "[EVT-03]" in result.stderr
    assert "in VEVENT on line 4" in result.stderr
    assert f"in {broken}" in result.stderr
