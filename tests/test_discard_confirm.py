import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _widget_with_discard(monkeypatch, dirty):
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._dirty = dirty
    calls = []
    w._discard_info = lambda: calls.append("discarded")
    return mt, w, calls


def test_discard_runs_when_confirmed(qapp, monkeypatch):
    mt, w, calls = _widget_with_discard(monkeypatch, dirty=True)
    monkeypatch.setattr(mt.QMessageBox, "question",
                        lambda *a, **k: mt.QMessageBox.StandardButton.Discard)
    w._confirm_discard()
    assert calls == ["discarded"]


def test_discard_skipped_when_cancelled(qapp, monkeypatch):
    mt, w, calls = _widget_with_discard(monkeypatch, dirty=True)
    monkeypatch.setattr(mt.QMessageBox, "question",
                        lambda *a, **k: mt.QMessageBox.StandardButton.Cancel)
    w._confirm_discard()
    assert calls == []


def test_no_prompt_or_discard_when_nothing_changed(qapp, monkeypatch):
    mt, w, calls = _widget_with_discard(monkeypatch, dirty=False)
    asked = []
    monkeypatch.setattr(mt.QMessageBox, "question",
                        lambda *a, **k: asked.append(True))
    w._confirm_discard()
    assert calls == [] and asked == []   # nothing to discard -> no dialog
