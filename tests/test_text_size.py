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
    try:
        theme.apply_theme(qapp, "dark", "xlarge")
        assert theme.current_text_scale() == pytest.approx(30 / 13)
        theme.apply_theme(qapp, "light")           # theme-only change
        assert theme.current_text_scale() == pytest.approx(30 / 13)
    finally:
        theme.apply_theme(qapp, "dark", "normal")  # restore the shared app
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
    # MainWindow reads the global scale set by apply_theme, not its settings dict.
    theme.set_text_size("xlarge")
    w = _main_window(tmp_path)
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
        self._alt_id_password = alt_id_password

    def exec(self):
        return True

    def result_settings(self):
        return {**self._settings, **self.result}

    def result_alt_id_password(self):
        # Like the real dialog, whose field opens pre-filled with the
        # session password and hands it straight back when it is untouched.
        return self._alt_id_password


@pytest.fixture(autouse=True)
def _reset_fake_dialog():
    """The fake's result is class state; clear it so it cannot leak."""
    yield
    _FakeSettingsDialog.result = {}


def _show_member_stub(w, center_id):
    """Put a MemberTabsWidget on the detail stack without a database.

    _set_detail() adds the member/events widget at index 1 and makes it
    current, so _open_settings' currentWidget() check sees this stub.
    """
    from PyQt6.QtWidgets import QWidget
    import gui.member_tabs as mt
    stub = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    QWidget.__init__(stub)
    stub._center_id = center_id
    w._detail_stack.addWidget(stub)
    w._detail_stack.setCurrentWidget(stub)
    return stub


def _saved(tmp_path):
    import json
    return json.loads((tmp_path / "settings.json").read_text())


def _arrange_reopen(w, monkeypatch, result, *, with_member=True):
    import gui.main_window as mw
    from gui import theme
    w.show()
    w._alt_id_password = "hunter2"
    w._last_center_id = 4242
    if with_member:
        _show_member_stub(w, 4242)
    _FakeSettingsDialog.result = result
    monkeypatch.setattr(mw, "SettingsDialog", _FakeSettingsDialog)
    monkeypatch.setattr(w, "_ok_to_leave_current", lambda: True)
    calls = []
    monkeypatch.setattr(theme, "apply_theme", lambda *a, **k: calls.append(a))
    return calls


def test_text_size_change_requests_reopen_on_current_member(qapp, tmp_path, monkeypatch):
    w = _main_window(tmp_path)
    calls = _arrange_reopen(w, monkeypatch, {"text_size": "large"})
    w._open_settings()
    assert w.reopen_requested is True
    assert w.reopen_member_id == 4242
    # The session password must survive the rebuild or alt IDs come back
    # as ciphertext in the new window.
    assert w.reopen_alt_id_password == "hunter2"
    assert w.isVisible() is False
    assert calls == []                 # live re-apply skipped; the rebuild does it
    assert _saved(tmp_path)["text_size"] == "large"


def test_reopen_drops_member_id_when_db_path_changes(qapp, tmp_path, monkeypatch):
    w = _main_window(tmp_path)
    _arrange_reopen(w, monkeypatch,
                    {"text_size": "large", "db_path": "other.accdb"})
    w._open_settings()
    assert w.reopen_requested is True
    # The id belongs to the old database — do not reopen it against the new one.
    assert w.reopen_member_id is None


def test_reopen_without_member_on_screen_has_no_member_id(qapp, tmp_path, monkeypatch):
    w = _main_window(tmp_path)
    # _last_center_id is still set, but nothing is on the detail stack.
    _arrange_reopen(w, monkeypatch, {"text_size": "large"}, with_member=False)
    w._open_settings()
    assert w.reopen_requested is True
    assert w.reopen_member_id is None


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
    from gui.theme import apply_theme
    try:
        w._open_settings()
        assert w.reopen_requested is False
        assert _saved(tmp_path)["theme"] == "light"
    finally:
        apply_theme(qapp, "dark")      # leave the shared app on the default


def test_jump_to_member_is_public(qapp, tmp_path):
    w = _main_window(tmp_path)
    assert callable(w.jump_to_member)


def test_set_alt_id_password_decrypts_loaded_corpus(qapp, tmp_path, monkeypatch):
    """The rebuilt window loads its corpus before run() hands it the session
    password; set_alt_id_password must decrypt what was already loaded."""
    import gui.main_window as mw
    w = _main_window(tmp_path)
    w._all_members = [{"center_id": 1, "alt_id": "CIPHER"}]
    seen = {}

    def fake_decrypt(members, key):
        seen["key"] = key
        for m in members:
            m["alt_id"] = "PLAIN"
    monkeypatch.setattr(mw, "decrypt_corpus_alt_ids", fake_decrypt)
    monkeypatch.setattr(w, "_alt_id_key", lambda: "KEY")
    w.set_alt_id_password("hunter2")
    assert w._alt_id_password == "hunter2"
    assert seen["key"] == "KEY"
    assert w._all_members[0]["alt_id"] == "PLAIN"


# ── entry point loop ───────────────────────────────────────────────────────

def test_run_rebuilds_window_once_when_requested(monkeypatch, tmp_path):
    import member_manager as mm

    created = []
    prev_local = []      # run()'s local `window` as seen when pass 2 constructs

    class StubWindow:
        def __init__(self, settings, path):
            if created:   # second pass: run() must have released the first window
                import inspect
                prev_local.append(inspect.currentframe().f_back.f_locals.get("window"))
            self.settings = settings
            self.jumped = None
            self.password = None
            self.order = []
            # First window asks to reopen on member 7; the second does not.
            self.reopen_requested = len(created) == 0
            self.reopen_member_id = 7 if self.reopen_requested else None
            self.reopen_alt_id_password = "hunter2" if self.reopen_requested else ""
            created.append(self)

        def show(self):
            self.order.append("show")

        def set_alt_id_password(self, pw):
            self.password = pw
            self.order.append("password")

        def jump_to_member(self, cid):
            self.jumped = cid
            self.order.append("jump")

    class StubApp:
        execs = 0

        def exec(self):
            StubApp.execs += 1
            return 0

    applied = []
    sizes = iter(["normal", "xlarge"])
    monkeypatch.setattr(mm, "MainWindow", StubWindow)
    monkeypatch.setattr(mm, "apply_theme",
                        lambda app, theme, text_size="normal": applied.append((theme, text_size)))
    monkeypatch.setattr(mm, "load_settings",
                        lambda path: {"theme": "light", "text_size": next(sizes),
                                      "events_db_path": "x"})
    monkeypatch.setattr(mm, "SETTINGS_PATH", str(tmp_path / "s.json"))

    code = mm.run(StubApp())

    assert code == 0
    assert StubApp.execs == 2
    assert len(created) == 2
    assert created[0].jumped is None
    assert created[1].jumped == 7
    assert created[0].password == "" and created[1].password == "hunter2"
    # The password must be restored before the member is reopened.
    assert created[1].order == ["password", "show", "jump"]
    assert applied == [("light", "normal"), ("light", "xlarge")]
    # The release line (`window = None`) is what makes this None; without it
    # the first window would still be referenced while the second is built.
    assert prev_local == [None]


def test_run_exits_immediately_and_propagates_the_exit_code(monkeypatch, tmp_path):
    import member_manager as mm

    created = []

    class StubWindow:
        reopen_requested = False
        reopen_member_id = None
        reopen_alt_id_password = ""

        def __init__(self, settings, path):
            self.jumped = None
            created.append(self)

        def show(self):
            pass

        def set_alt_id_password(self, pw):
            pass

        def jump_to_member(self, cid):
            self.jumped = cid

    class StubApp:
        def __init__(self):
            self.execs = 0

        def exec(self):
            self.execs += 1
            return 3

    monkeypatch.setattr(mm, "MainWindow", StubWindow)
    monkeypatch.setattr(mm, "apply_theme", lambda *a, **k: None)
    monkeypatch.setattr(mm, "load_settings",
                        lambda path: {"theme": "dark", "events_db_path": "x"})
    monkeypatch.setattr(mm, "SETTINGS_PATH", str(tmp_path / "s.json"))
    app = StubApp()
    assert mm.run(app) == 3
    assert app.execs == 1 and len(created) == 1 and created[0].jumped is None


# ── no literal font sizes left in widget code ──────────────────────────────

# Files converted so far; later tasks extend this list until it covers every
# widget module. theme.py (the QSS) and profile_print.py (printed HTML keeps
# its own point scale; only its on-screen printer picker scales) are excluded
# by design.
_CONVERTED = [
    "gui/member_tabs.py",
    "gui/main_window.py",
    "gui/info_layout_editor.py",
    "gui/bookmarks_panel.py",
    "gui/notifications.py",
    "gui/confirm_changes.py",
    "gui/events_view.py",
    "gui/expiring_report.py",
    "gui/address_autocomplete.py",
    "gui/time_range_editor.py",
]

_LITERAL_FONT_SIZE = re.compile(r"font-size:\s*\d+px")
_LITERAL_ROW_HEIGHT = re.compile(r"setDefaultSectionSize\(\s*\d+\s*\)")
# Badge/button caps, icon-button widths and note-editor heights that Task 8
# converted; a literal here means a text-holding dimension stopped scaling.
_LITERAL_TEXT_DIMENSION = re.compile(
    r"setMaximumHeight\(\s*26\s*\)|setFixedWidth\(\s*2[68]\s*\)|setFixedHeight\(\s*6[04]\s*\)")
# Point-size fonts (events-log timestamps, time-slider ticks) must go through px().
_LITERAL_POINT_SIZE = re.compile(r"setPointSize\(\s*\d|QFont\([^)]*,\s*\d")


@pytest.mark.parametrize("rel", _CONVERTED)
def test_no_literal_font_sizes_or_row_heights(rel):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(root, rel), encoding="utf-8").read()
    assert not _LITERAL_FONT_SIZE.findall(src), rel
    assert not _LITERAL_ROW_HEIGHT.findall(src), rel
    assert not _LITERAL_TEXT_DIMENSION.findall(src), rel
    assert not _LITERAL_POINT_SIZE.findall(src), rel


def test_member_table_row_height_follows_scale(qapp):
    """Same bare-widget setup as tests/test_emergency_table.py::_info_tab_with:
    _make_info_tab builds the emergency-contacts table without a database."""
    from PyQt6.QtWidgets import QLabel
    from gui import theme
    import gui.member_tabs as mt
    theme.set_text_size("large")
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._member = {"first_name": "A", "last_name": "B"}
    w._center_id = 1
    w._db_path = ""
    w._api_key = ""
    w._enrollments = []
    w._authorizations = []
    w._emergency_contacts = [{"id": 1, "full_name": "Andy Lau",
                              "phone": "(917) 628-0459", "relationship": "Son"}]
    w._emergency_badge = QLabel()
    w._test_outer = w._make_info_tab()   # keep a ref so children aren't GC'd
    assert w._emergency_table.verticalHeader().defaultSectionSize() == theme.px(34) == 65


def test_popup_panels_and_slider_follow_scale(qapp):
    from gui import theme
    theme.set_text_size("large")
    from gui.bookmarks_panel import BookmarksPanel
    from gui.notifications import NotificationsPanel
    from gui.time_range_editor import RangeSlider
    from gui.confirm_changes import ConfirmChangesDialog
    assert BookmarksPanel([]).width() == theme.px(380) == 731
    assert NotificationsPanel([], [], {}).width() == theme.px(360) == 692
    s = RangeSlider()
    assert s._handle_r == theme.px(9) == 17
    assert s.minimumHeight() >= theme.px(60) == 115
    d = ConfirmChangesDialog("Chan, Mary", [("Notes", "a", "b")])
    assert d.minimumWidth() == theme.px(760) == 1462
