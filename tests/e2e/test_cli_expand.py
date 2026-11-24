import io
from pathlib import Path

import pytest

from recurkit.cli import main

TEAM = str(Path(__file__).resolve().parents[1] / "data" / "ics" / "team.ics")


def _run(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(list(args), out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def test_expand_lists_the_design_document_dates_in_kyiv() -> None:
    code, out, err = _run(
        "expand", TEAM, "--from", "2026-01-01", "--to", "2026-06-30", "--tz", "Europe/Kyiv"
    )
    assert (code, err) == (0, "")
    planning = [line[:10] for line in out.splitlines() if line.endswith("Monthly planning")]
    assert planning == [
        "2026-01-13",
        "2026-02-10",
        "2026-03-10",
        "2026-04-14",
        "2026-05-12",
        "2026-06-09",
    ]
    assert "2026-04-14 10:00-11:00  Monthly planning" in out.splitlines()


def test_expand_shows_times_in_the_requested_zone_or_utc() -> None:
    _, new_york, _ = _run(
        "expand", TEAM, "--from", "2026-01-13", "--to", "2026-01-13", "--tz", "America/New_York"
    )
    assert new_york == "2026-01-13 03:00-04:00  Monthly planning\n"
    _, utc, _ = _run("expand", TEAM, "--from", "2026-01-13", "--to", "2026-01-13")
    assert utc == "2026-01-13 08:00-09:00  Monthly planning\n"


def test_expand_window_includes_whole_first_and_last_day() -> None:
    _, out, _ = _run(
        "expand", TEAM, "--from", "2026-02-10", "--to", "2026-03-10", "--tz", "Europe/Kyiv"
    )
    assert [line[:10] for line in out.splitlines()] == ["2026-02-10", "2026-03-10"]
    _, out, _ = _run(
        "expand", TEAM, "--from", "2026-02-11", "--to", "2026-03-09", "--tz", "Europe/Kyiv"
    )
    assert out == ""


def test_expand_prints_all_day_spans_and_skips_cancelled_events() -> None:
    _, out, _ = _run("expand", TEAM, "--from", "2026-01-01", "--to", "2026-12-31")
    lines = out.splitlines()
    assert "2026-05-18..2026-05-19 all day  Offsite, Lviv" in lines
    assert not any("Retro" in line for line in lines)


def test_expand_reports_missing_files_and_bad_windows() -> None:
    code, out, err = _run("expand", "nowhere.ics", "--from", "2026-01-01", "--to", "2026-01-31")
    assert (code, out) == (1, "")
    assert err.startswith("recurkit: error: cannot read nowhere.ics")
    code, _, err = _run("expand", TEAM, "--from", "2026-02-01", "--to", "2026-01-31")
    assert code == 1
    assert "before --from" in err
    code, _, err = _run(
        "expand", TEAM, "--from", "2026-01-01", "--to", "2026-01-31", "--tz", "Mars/Base"
    )
    assert code == 1
    assert "Mars/Base" in err


def test_expand_rejects_malformed_dates_as_usage_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["expand", TEAM, "--from", "01.01.2026", "--to", "2026-01-31"])
    assert caught.value.code == 2
    assert "expected a date like 2026-01-31" in capsys.readouterr().err
