import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ir_join_diff


class DummyGalaxyIR:
    def good_join(self) -> list:
        return []

    def good_join_with_defaults(self, a: int = 1, b: int = 2) -> list:
        return []

    def bad_join_required_arg(self, a: int) -> list:
        return []

    def _private_join(self) -> list:
        return []


def test_joins() -> None:
    j = ir_join_diff.joins(DummyGalaxyIR)
    assert "good_join" in j
    assert "good_join_with_defaults" in j
    assert "bad_join_required_arg" not in j
    assert "_private_join" not in j


@dataclasses.dataclass
class DummyRow:
    a: int
    b: str


def test_compare_rows_list_multiset() -> None:
    old = [DummyRow(1, "x"), DummyRow(1, "x"), DummyRow(2, "y")]
    new = [DummyRow(2, "y"), DummyRow(1, "x"), DummyRow(3, "z")]

    removed, added = ir_join_diff.compare_rows(old, new)
    assert len(removed) == 1
    assert "x" in removed[0]
    assert len(added) == 1
    assert "z" in added[0]


def test_compare_rows_dict() -> None:
    old = {"key1": DummyRow(1, "x"), "key2": DummyRow(2, "y")}
    new = {"key1": DummyRow(1, "x"), "key3": DummyRow(3, "z")}

    removed, added = ir_join_diff.compare_rows(old, new)
    assert len(removed) == 1
    assert "y" in removed[0]
    assert len(added) == 1
    assert "z" in added[0]
