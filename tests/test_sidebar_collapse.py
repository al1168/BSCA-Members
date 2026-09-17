"""Collapsible member list: a toolbar toggle (and Ctrl+B) hides the sidebar
so the detail panel gets the full window width — the way to fit Large /
Extra Large text on a small screen. The state is remembered in settings so
it survives the text-size rebuild and the next launch."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _main_window(tmp_path, **settings):
    from gui.main_window import MainWindow
    return MainWindow({"db_path": "", "theme": "dark", **settings},
                      str(tmp_path / "settings.json"))


def test_default_setting_is_expanded():
    from settings import DEFAULT_SETTINGS
    assert DEFAULT_SETTINGS["sidebar_collapsed"] is False


def test_sidebar_visible_by_default_and_toggle_hides_it(qapp, tmp_path):
    w = _main_window(tmp_path)
    assert not w._sidebar.isHidden()
    w.toggle_sidebar()
    assert w._sidebar.isHidden()
    w.toggle_sidebar()
    assert not w._sidebar.isHidden()


def test_collapsed_sidebar_frees_its_width_for_the_detail_panel(qapp, tmp_path):
    from gui import theme
    w = _main_window(tmp_path)
    layout = w.centralWidget().layout()
    before = layout.minimumSize().width()
    w.toggle_sidebar()
    # The hidden sidebar drops out of the layout entirely: the window's
    # minimum width shrinks by the full sidebar width, so a screen that could
    # not fit sidebar + profile at Extra Large can fit the profile alone.
    assert layout.minimumSize().width() == before - theme.px(220)


def test_toolbar_button_reflects_state(qapp, tmp_path):
    w = _main_window(tmp_path)
    assert "Hide" in w._btn_sidebar.toolTip()
    assert w._btn_sidebar.text().startswith("◀")
    w._btn_sidebar.click()
    assert w._sidebar.isHidden()
    assert "Show" in w._btn_sidebar.toolTip()
    assert w._btn_sidebar.text().startswith("▶")


def test_toggle_saves_state_and_new_window_restores_it(qapp, tmp_path):
    w = _main_window(tmp_path)
    w.toggle_sidebar()
    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert saved["sidebar_collapsed"] is True
    w2 = _main_window(tmp_path, sidebar_collapsed=True)
    assert w2._sidebar.isHidden()
    assert w2._btn_sidebar.text().startswith("▶")
    w2.toggle_sidebar()
    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert saved["sidebar_collapsed"] is False


def test_ctrl_b_toggles_the_sidebar(qapp, tmp_path):
    from PyQt6.QtGui import QShortcut, QKeySequence
    w = _main_window(tmp_path)
    keys = [s.key() for s in w.findChildren(QShortcut)]
    assert QKeySequence("Ctrl+B") in keys


def test_theme_styles_the_toggle_like_the_other_toolbar_buttons():
    from gui.theme import build_qss, DARK
    qss = build_qss(DARK)
    assert "QPushButton#btn_sidebar_toggle" in qss
    assert "QPushButton#btn_sidebar_toggle:hover" in qss


def test_collapsing_refits_a_maximized_window_to_the_screen(qapp, tmp_path):
    """On a screen too narrow for list + profile the maximized window is
    forced wider than the screen, so the toolbar's right end hangs off it.
    Collapsing the list lowers the minimum, but Windows leaves a maximized
    window at its size until it is maximized again — so the toggle must
    re-apply the maximized state, and only when the window is maximized."""
    from PyQt6.QtCore import Qt
    w = _main_window(tmp_path)
    calls = []
    w.setWindowState = lambda st: calls.append(st)     # spy on the refit
    w._is_maximized = lambda: False                    # normal window: no refit
    w.toggle_sidebar()
    assert calls == []
    w._is_maximized = lambda: True
    w.toggle_sidebar()
    assert calls == [Qt.WindowState.WindowNoState, Qt.WindowState.WindowMaximized]
