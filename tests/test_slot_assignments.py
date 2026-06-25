from __future__ import annotations

from services.slot_assignments import SlotAssignments


def _store(tmp_path) -> SlotAssignments:
    s = SlotAssignments(str(tmp_path / "data" / "slot_machine.json"))
    s.load()
    return s


def test_empty_on_missing_file(tmp_path):
    s = _store(tmp_path)
    assert s.get_all() == {}


def test_tolerates_list_content(tmp_path):
    path = tmp_path / "data" / "slot_machine.json"
    path.parent.mkdir(parents=True)
    path.write_text("[]", encoding="utf-8")
    s = SlotAssignments(str(path))
    s.load()
    assert s.get_all() == {}


def test_set_many_persists_and_roundtrips(tmp_path):
    s1 = _store(tmp_path)
    s1.set_many({"Machine 7900|1": "12345", "Machine 7900|2": ""})

    s2 = SlotAssignments(s1._path)
    s2.load()
    assert s2.get_all() == {"Machine 7900|1": "12345"}


def test_set_many_empty_value_clears_slot(tmp_path):
    s = _store(tmp_path)
    s.set_many({"Machine 7900|1": "12345"})
    assert s.get_all() == {"Machine 7900|1": "12345"}

    s.set_many({"Machine 7900|1": ""})
    assert s.get_all() == {}
