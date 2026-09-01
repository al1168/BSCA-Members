import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _widget(member):
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._member = member
    return w


def test_refresh_hides_label_when_alt_id_unset(qapp):
    from PyQt6.QtWidgets import QLabel
    w = _widget({"alt_id": None})
    w._alt_id_label = QLabel()
    w._refresh_alt_id_label()
    assert w._alt_id_label.text() == ""
    assert w._alt_id_label.isHidden()


def test_refresh_shows_alt_id_in_label(qapp):
    from PyQt6.QtWidgets import QLabel
    w = _widget({"alt_id": 4321})
    w._alt_id_label = QLabel()
    w._refresh_alt_id_label()
    assert w._alt_id_label.text() == "Alt ID 4321"
    assert not w._alt_id_label.isHidden()


def test_refresh_noop_before_header_built(qapp):
    # Must not raise when called on a widget whose header isn't built yet.
    w = _widget({"alt_id": 4321})
    w._refresh_alt_id_label()


# ── the '+ alt id' affordance swaps with the red label ─────────────────────
def _widget_with_header(member):
    from PyQt6.QtWidgets import QLabel, QPushButton
    w = _widget(member)
    w._alt_id_label = QLabel()
    w._alt_id_add_btn = QPushButton()
    return w


def test_add_button_shown_when_alt_id_unset(qapp):
    w = _widget_with_header({"alt_id": None})
    w._refresh_alt_id_label()
    assert w._alt_id_label.isHidden()
    assert not w._alt_id_add_btn.isHidden()


def test_add_button_hidden_when_alt_id_set(qapp):
    w = _widget_with_header({"alt_id": 4321})
    w._refresh_alt_id_label()
    assert not w._alt_id_label.isHidden()
    assert w._alt_id_label.text() == "Alt ID 4321"
    assert w._alt_id_add_btn.isHidden()


# ── clicking the red label opens the edit dialog ───────────────────────────
def test_alt_id_label_emits_clicked_on_left_press(qapp):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from gui.member_tabs import _AltIdLabel
    lbl = _AltIdLabel()
    seen = []
    lbl.clicked.connect(lambda: seen.append(1))
    QTest.mouseClick(lbl, Qt.MouseButton.LeftButton)
    assert seen == [1]
    QTest.mouseClick(lbl, Qt.MouseButton.RightButton)   # right click ignored
    assert seen == [1]


# ── session decryption key: the label shows the decrypted value ────────────
import pytest


@pytest.fixture(scope="module")
def fpe_key():
    from db.alt_id_crypto import derive_key
    return derive_key("test-pass")   # PBKDF2 is slow — derive once per module


def test_label_shows_decrypted_value_when_key_set(qapp, fpe_key):
    from PyQt6.QtWidgets import QLabel
    from db.alt_id_crypto import encrypt_alt_id
    w = _widget({"alt_id": encrypt_alt_id(fpe_key, 4321)})
    w._alt_id_key = fpe_key
    w._alt_id_label = QLabel()
    w._refresh_alt_id_label()
    assert w._alt_id_label.text() == "Alt ID 4321"


def test_label_shows_raw_when_no_key(qapp, fpe_key):
    from PyQt6.QtWidgets import QLabel
    from db.alt_id_crypto import encrypt_alt_id
    cipher = encrypt_alt_id(fpe_key, 4321)
    w = _widget({"alt_id": cipher})       # no _alt_id_key attribute at all
    w._alt_id_label = QLabel()
    w._refresh_alt_id_label()
    assert w._alt_id_label.text() == f"Alt ID {cipher}"


def test_label_shows_raw_for_out_of_domain_value(qapp, fpe_key):
    from PyQt6.QtWidgets import QLabel
    w = _widget({"alt_id": 2**31 + 5})    # can't decrypt — show raw, no raise
    w._alt_id_key = fpe_key
    w._alt_id_label = QLabel()
    w._refresh_alt_id_label()
    assert w._alt_id_label.text() == f"Alt ID {2**31 + 5}"


# ── edit path: what the user types is encrypted before the DB write ────────
def test_edit_alt_id_encrypts_on_save(qapp, fpe_key, monkeypatch):
    from PyQt6.QtWidgets import QWidget
    import gui.member_tabs as mt
    import db.members
    from db.alt_id_crypto import encrypt_alt_id

    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    QWidget.__init__(w)                   # init the C++ side so signals work
    w._member = {"alt_id": None}
    w._alt_id_key = fpe_key
    w._center_id = 1
    w._db_path = "unused.accdb"
    w._log_event = lambda *a, **k: None

    monkeypatch.setattr(mt.MemberTabsWidget, "_open_alt_id_dialog",
                        lambda self, existing=None: (True, 4321))
    written = {}
    monkeypatch.setattr(
        db.members, "set_member_alt_id",
        lambda cid, alt, db_path: written.update(cid=cid, alt=alt))

    w._edit_alt_id()

    assert written["alt"] == encrypt_alt_id(fpe_key, 4321)
    assert w._member["alt_id"] == written["alt"]   # memory holds ciphertext
