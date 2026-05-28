from __future__ import annotations

import json
import os

import pytest

from services.test_registry import TestRegistry


def _registry(tmp_path) -> TestRegistry:
    r = TestRegistry(str(tmp_path / "data" / "test_registry.json"))
    r.load()
    return r


def test_add_and_get_all(tmp_path):
    r = _registry(tmp_path)
    r.add("12345")
    entries = r.get_all()
    assert len(entries) == 1
    assert entries[0]["test_number"] == "12345"


def test_add_default_status_active(tmp_path):
    r = _registry(tmp_path)
    r.add("12345")
    assert r.get_all()[0]["status"] == "active"


def test_add_explicit_planned(tmp_path):
    r = _registry(tmp_path)
    r.add("12345", status="planned")
    assert r.get_all()[0]["status"] == "planned"


def test_get_active_filters_planned(tmp_path):
    r = _registry(tmp_path)
    r.add("11111", status="active")
    r.add("22222", status="planned")
    active = r.get_active()
    assert "11111" in active
    assert "22222" not in active


def test_remove(tmp_path):
    r = _registry(tmp_path)
    r.add("12345")
    r.remove("12345")
    assert r.get_all() == []


def test_set_status(tmp_path):
    r = _registry(tmp_path)
    r.add("12345", status="active")
    r.set_status("12345", "planned")
    assert r.get_all()[0]["status"] == "planned"


def test_persistence_roundtrip(tmp_path):
    r1 = _registry(tmp_path)
    r1.add("99999", status="active")

    r2 = TestRegistry(r1._path)
    r2.load()
    entries = r2.get_all()
    assert len(entries) == 1
    assert entries[0]["test_number"] == "99999"
    assert entries[0]["status"] == "active"


def test_no_duplicates(tmp_path):
    r = _registry(tmp_path)
    r.add("12345")
    r.add("12345")
    assert len(r.get_all()) == 1


def test_empty_on_missing_file(tmp_path):
    r = TestRegistry(str(tmp_path / "data" / "test_registry.json"))
    r.load()
    assert r.get_all() == []


def test_creates_data_directory(tmp_path):
    data_dir = tmp_path / "data"
    assert not data_dir.exists()
    r = TestRegistry(str(data_dir / "test_registry.json"))
    r.load()
    r.add("12345")
    assert data_dir.exists()
