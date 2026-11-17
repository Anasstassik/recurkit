import pytest

from recurkit import RecurKitError, RuleSyntaxError, RuleValidationError, TimeZoneError


def test_all_library_errors_share_a_base_class() -> None:
    for error in (
        RuleSyntaxError("bad part"),
        RuleValidationError("RRULE-07", "COUNT and UNTIL"),
        TimeZoneError("unknown zone", tzid="Mars/Olympus"),
    ):
        assert isinstance(error, RecurKitError)
    assert issubclass(RuleSyntaxError, ValueError)
    assert issubclass(RuleValidationError, ValueError)


def test_syntax_error_reports_position() -> None:
    error = RuleSyntaxError("unknown rule part 'FOO'", text="FREQ=DAILY;FOO=1", position=11)
    assert error.position == 11
    assert error.text == "FREQ=DAILY;FOO=1"
    assert str(error) == "unknown rule part 'FOO' (at position 11)"
    assert str(RuleSyntaxError("empty rule")) == "empty rule"


def test_validation_error_carries_requirement_id() -> None:
    error = RuleValidationError("RRULE-07", "UNTIL and COUNT must not occur together")
    assert error.requirement_id == "RRULE-07"
    assert str(error) == "[RRULE-07] UNTIL and COUNT must not occur together"
    with pytest.raises(ValueError, match="malformed requirement id"):
        RuleValidationError("rrule7", "lowercase id is rejected")
