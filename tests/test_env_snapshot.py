"""EnvSnapshot filtering edge cases."""

from __future__ import annotations

from serverkit.env.vars import EnvSnapshot


def test_keys_matching_empty_returns_empty():
    snap = EnvSnapshot({"A": "1", "B": "2"})
    assert snap.keys_matching("").all() == {}
    assert snap.keys_matching("   ").all() == {}


def test_keys_matching_substring_of_key():
    snap = EnvSnapshot({"PATH": "x", "PATHEXT": "y", "OTHER": "z"})
    out = snap.keys_matching("path").all()
    assert set(out) == {"PATH", "PATHEXT"}


def test_contains_empty_returns_empty():
    snap = EnvSnapshot({"A": "hello", "B": "world"})
    assert snap.contains("").all() == {}
    assert snap.contains("  ").all() == {}


def test_contains_matches_value():
    snap = EnvSnapshot({"ONEDRIVE": r"C:\Users\me\OneDrive", "X": "nope"})
    out = snap.contains("OneDrive").all()
    assert out == {"ONEDRIVE": r"C:\Users\me\OneDrive"}
