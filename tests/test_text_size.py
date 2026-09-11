"""App-wide text size mode: one scale factor drives every on-screen font size
and the fixed dimensions that hold text."""
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


# ── scale model ────────────────────────────────────────────────────────────

def test_text_sizes_and_factors():
    from gui.theme import TEXT_SIZES, BASE_PX, text_scale_for
    assert TEXT_SIZES == {"normal": 13, "large": 25, "xlarge": 30}
    assert BASE_PX == 13
    assert text_scale_for("normal") == 1.0
    assert text_scale_for("large") == pytest.approx(25 / 13)
    assert text_scale_for("xlarge") == pytest.approx(30 / 13)
    assert text_scale_for("bogus") == 1.0


def test_px_rounds_to_nearest_pixel():
    from gui.theme import set_text_size, px, current_text_scale
    assert current_text_scale() == 1.0
    assert px(13) == 13 and px(9) == 9
    set_text_size("large")
    assert [px(n) for n in (9, 10, 12, 13, 20)] == [17, 19, 23, 25, 38]
    set_text_size("xlarge")
    assert [px(n) for n in (9, 10, 12, 13, 20)] == [21, 23, 28, 30, 46]
    assert px(220) == 508          # sidebar width at Extra Large (Task 6)


def test_set_text_size_returns_scale_and_ignores_unknown():
    from gui.theme import set_text_size, current_text_scale
    assert set_text_size("xlarge") == pytest.approx(30 / 13)
    assert set_text_size("nonsense") == 1.0
    assert current_text_scale() == 1.0


def test_apply_theme_sets_scale_only_when_asked(qapp):
    from gui import theme
    theme.apply_theme(qapp, "dark", "xlarge")
    assert theme.current_text_scale() == pytest.approx(30 / 13)
    theme.apply_theme(qapp, "light")               # theme-only change
    assert theme.current_text_scale() == pytest.approx(30 / 13)
    theme.apply_theme(qapp, "dark", "normal")
    assert theme.current_text_scale() == 1.0


# ── build_qss scaling ──────────────────────────────────────────────────────

def test_qss_default_scale_is_unchanged_and_has_no_literal_sizes_left():
    from gui.theme import build_qss, DARK, LIGHT
    for tokens in (DARK, LIGHT):
        qss = build_qss(tokens)
        assert qss == build_qss(tokens, 1.0)
        assert "font-size: 13px;" in qss           # base rule intact at Normal
        assert 'QLineEdit#info_field[fsize="xlarge"] { font-size: 20px; }' in qss
        assert 'QLabel#field_label[lsize="large"] { font-size: 13px; }' in qss
    # The generator's source carries no literal font-size — every rule goes
    # through p()/_scaled, so a hand-written `font-size: 12px` cannot sneak in.
    import inspect
    import gui.theme
    assert not re.search(r"font-size:\s*\d", inspect.getsource(gui.theme))


def test_qss_scales_every_font_size():
    from gui.theme import build_qss, DARK, LIGHT, text_scale_for, _scaled

    def sizes(qss):
        return [int(s) for s in re.findall(r"font-size: (\d+)px", qss)]

    for tokens in (DARK, LIGHT):
        normal = build_qss(tokens)
        large = build_qss(tokens, text_scale_for("large"))
        xlarge = build_qss(tokens, text_scale_for("xlarge"))
        assert len(sizes(normal)) >= 55
        # Every rule, in order, is exactly the Normal value through _scaled —
        # a single hand-written literal among the rules fails this.
        assert sizes(large) == [_scaled(n, 25 / 13) for n in sizes(normal)]
        assert sizes(xlarge) == [_scaled(n, 30 / 13) for n in sizes(normal)]
        # Readability anchors.
        assert "font-size: 25px;" in large and "font-size: 23px;" in large
        assert "font-size: 30px;" in xlarge and "font-size: 28px;" in xlarge
        assert 'QLineEdit#info_field[fsize="xlarge"] { font-size: 46px; }' in xlarge
        assert 'QLabel#field_label[lsize="large"] { font-size: 30px; }' in xlarge
        # Paddings and radii are not scaled.
        assert "padding: 7px 16px;" in xlarge and "border-radius: 7px;" in xlarge


def test_rendered_label_reports_scaled_pixel_size(qapp):
    from PyQt6.QtWidgets import QLabel
    from gui.theme import build_qss, DARK, text_scale_for
    lab = QLabel("Members")
    lab.setStyleSheet(build_qss(DARK, text_scale_for("xlarge")))
    lab.style().unpolish(lab)
    lab.style().polish(lab)
    assert lab.font().pixelSize() == 30


# ── settings dialog ────────────────────────────────────────────────────────

_BASE_SETTINGS = {"db_path": "", "events_db_path": "", "theme": "dark",
                  "google_api_key": "", "show_row_ids": False}


@pytest.mark.parametrize("name", ["normal", "large", "xlarge"])
def test_settings_dialog_roundtrips_text_size(qapp, name):
    from gui.settings_dialog import SettingsDialog
    dlg = SettingsDialog({**_BASE_SETTINGS, "text_size": name})
    assert dlg.result_settings()["text_size"] == name


def test_settings_dialog_text_size_defaults_to_normal_when_missing(qapp):
    from gui.settings_dialog import SettingsDialog
    dlg = SettingsDialog(dict(_BASE_SETTINGS))
    assert dlg._radio_size_normal.isChecked()
    assert dlg.result_settings()["text_size"] == "normal"
    dlg._radio_size_xlarge.setChecked(True)
    assert dlg.result_settings()["text_size"] == "xlarge"
    # Unknown values (hand-edited settings file) fall back to Normal.
    assert SettingsDialog({**_BASE_SETTINGS, "text_size": "huge"}
                          ).result_settings()["text_size"] == "normal"


# ── main window ────────────────────────────────────────────────────────────

def _main_window(tmp_path, **settings):
    from gui.main_window import MainWindow
    return MainWindow({"db_path": "", "theme": "dark", **settings},
                      str(tmp_path / "settings.json"))


def test_sidebar_and_startup_size_follow_text_scale(qapp, tmp_path):
    from gui import theme
    theme.set_text_size("xlarge")
    w = _main_window(tmp_path, text_size="xlarge")
    from PyQt6.QtWidgets import QWidget
    sidebar = w.findChild(QWidget, "sidebar")
    # setFixedWidth pins min == max; width() is unreliable before show().
    assert sidebar.minimumWidth() == sidebar.maximumWidth() == theme.px(220) == 508
    assert w._member_counts.styleSheet() == f"font-size:{theme.px(12)}px;"


class _FakeSettingsDialog:
    """Stands in for SettingsDialog: accepted immediately with a fixed result."""
    result = {}

    def __init__(self, settings, parent=None, alt_id_password=""):
        self._settings = dict(settings)

    def exec(self):
        return True

    def result_settings(self):
        return {**self._settings, **self.result}

    def result_alt_id_password(self):
        return ""


def _saved(tmp_path):
    import json
    return json.loads((tmp_path / "settings.json").read_text())


def test_text_size_change_requests_reopen_on_current_member(qapp, tmp_path, monkeypatch):
    import gui.main_window as mw
    w = _main_window(tmp_path)
    w._last_center_id = 4242
    _FakeSettingsDialog.result = {"text_size": "large"}
    monkeypatch.setattr(mw, "SettingsDialog", _FakeSettingsDialog)
    monkeypatch.setattr(w, "_ok_to_leave_current", lambda: True)
    w._open_settings()
    assert w.reopen_requested is True
    assert w.reopen_member_id == 4242
    assert _saved(tmp_path)["text_size"] == "large"


def test_cancelling_discard_reverts_text_size_but_saves_the_rest(qapp, tmp_path, monkeypatch):
    import gui.main_window as mw
    w = _main_window(tmp_path)
    _FakeSettingsDialog.result = {"text_size": "xlarge", "show_row_ids": True}
    monkeypatch.setattr(mw, "SettingsDialog", _FakeSettingsDialog)
    monkeypatch.setattr(w, "_ok_to_leave_current", lambda: False)
    w._open_settings()
    assert w.reopen_requested is False
    saved = _saved(tmp_path)
    assert saved["text_size"] == "normal"
    assert saved["show_row_ids"] is True


def test_theme_only_change_does_not_reopen(qapp, tmp_path, monkeypatch):
    import gui.main_window as mw
    w = _main_window(tmp_path)
    _FakeSettingsDialog.result = {"theme": "light"}
    monkeypatch.setattr(mw, "SettingsDialog", _FakeSettingsDialog)
    w._open_settings()
    assert w.reopen_requested is False
    assert _saved(tmp_path)["theme"] == "light"
    from gui.theme import apply_theme
    apply_theme(qapp, "dark")          # leave the shared app on the default


def test_jump_to_member_is_public(qapp, tmp_path):
    w = _main_window(tmp_path)
    assert callable(w.jump_to_member)
