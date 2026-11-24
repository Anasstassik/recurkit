import io
import subprocess
import sys
from pathlib import Path

import pytest

from recurkit import __version__
from recurkit.cli import main

ROOT = Path(__file__).resolve().parents[2]


def _run(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(list(args), out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def test_validate_runs_as_a_process_on_the_design_document_rule() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "recurkit", "validate", "FREQ=MONTHLY;BYDAY=2TU;COUNT=6"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.splitlines()[0] == "valid: FREQ=MONTHLY;COUNT=6;BYDAY=2TU"
    assert "6 times" in result.stdout
    assert result.stderr == ""


def test_rrule_07_cli_reports_the_requirement_id() -> None:
    code, out, err = _run("validate", "FREQ=DAILY;COUNT=3;UNTIL=20261231")
    assert (code, out) == (1, "")
    assert err.startswith("recurkit: invalid: [RRULE-07]")
    code, _, err = _run("validate", "FREQ=WEEKLY;BYDAY=2TU")
    assert code == 1
    assert "[RRULE-13]" in err


def test_validate_reports_syntax_errors_and_bad_dtstart() -> None:
    code, _, err = _run("validate", "FREQ=DAILY;;COUNT=x")
    assert code == 1
    assert err.startswith("recurkit: syntax error:")
    code, _, err = _run("validate", "FREQ=DAILY", "--dtstart", "tomorrow")
    assert code == 1
    assert err.startswith("recurkit: error: --dtstart:")


def test_validate_uses_dtstart_time_zone_and_until_form() -> None:
    code, out, _ = _run(
        "validate", "FREQ=WEEKLY;BYDAY=TU", "--dtstart", "2026-01-06T10:00", "--tz", "Europe/Kyiv"
    )
    assert code == 0
    assert "at 10:00" in out
    assert _run("validate", "FREQ=DAILY;UNTIL=20261231T000000Z")[0] == 0
    assert _run("validate", "FREQ=DAILY;UNTIL=20261231")[0] == 0
    assert _run("validate", "FREQ=DAILY", "--dtstart", "2026-01-06")[0] == 0
    assert _run("validate", "FREQ=DAILY", "--dtstart", "20260106T100000Z")[0] == 0
    code, _, err = _run("validate", "FREQ=DAILY", "--dtstart", "2026-01-06T10:00+02:00")
    assert code == 1
    assert "use --tz" in err
    code, _, err = _run("validate", "FREQ=DAILY", "--tz", "Mars/Olympus")
    assert code == 1
    assert "Mars/Olympus" in err


def test_usage_errors_exit_with_code_2_and_version_is_printed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for argv in ([], ["explode"], ["validate"]):
        with pytest.raises(SystemExit) as caught:
            main(argv)
        assert caught.value.code == 2
    with pytest.raises(SystemExit) as caught:
        main(["--version"])
    assert caught.value.code == 0
    assert capsys.readouterr().out.strip() == f"recurkit {__version__}"
