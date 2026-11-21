import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIREMENT_ROW = re.compile(r"^- ([A-Z]+-\d{2}):", re.MULTILINE)
CLOCK_CALLS = {"now", "utcnow", "today"}


def _requirement_ids() -> list[str]:
    return REQUIREMENT_ROW.findall((ROOT / "docs" / "requirements.md").read_text("utf-8"))


def _test_names() -> set[str]:
    names: set[str] = set()
    for path in (ROOT / "tests").rglob("test_*.py"):
        tree = ast.parse(path.read_text("utf-8"))
        names.update(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        )
    return names


def test_catalog_lists_unique_ids() -> None:
    ids = _requirement_ids()
    assert len(ids) >= 40
    assert len(ids) == len(set(ids))


def test_every_requirement_id_has_a_named_test() -> None:
    names = _test_names()
    missing = []
    for requirement_id in _requirement_ids():
        token = re.compile(rf"(^|_){requirement_id.lower().replace('-', '_')}(_|$)")
        if not any(token.search(name) for name in names):
            missing.append(requirement_id)
    assert missing == []


def test_library_never_reads_the_clock() -> None:
    offenders = []
    for path in sorted((ROOT / "recurkit").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text("utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in CLOCK_CALLS
            ):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert offenders == []
