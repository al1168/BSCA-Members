# Google Places Address Autocomplete + Lat/Long Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Google Places autocomplete to the member address field in the Add-Member wizard and the Edit (Info) tab, and persist the picked place's `longitude,latitude` to the `Contacts.[Long Lat]` column.

**Architecture:** A reusable `gui/address_autocomplete.py::AddressAutocomplete` widget does async lookups via Qt's `QNetworkAccessManager` (no new dependency) and exposes a pure, unit-tested `parse_place_location` helper. The wizard and Info tab use the widget; coordinates are written via an extended `INSERT_CONTACT` (new members) and an isolated `set_member_long_lat` (edits, only when a suggestion is picked). The API key lives in settings.

**Tech Stack:** Python 3.11, PyQt6 (incl. `PyQt6.QtNetwork`), pyodbc, pytest + pytest-qt. **No new dependencies.**

---

## File Map

```
db/members.py                    modify — INSERT_CONTACT [Long Lat]; insert_member long_lat; SET_LONG_LAT + set_member_long_lat
settings.py                      modify — google_api_key default
gui/settings_dialog.py           modify — Google API key field
gui/address_autocomplete.py      create — parse_place_location + AddressAutocomplete widget
gui/wizard/step_contact.py       modify — use AddressAutocomplete; collect long_lat
gui/wizard/wizard.py             modify — thread api_key; pass long_lat to insert_member
gui/member_tabs.py               modify — api_key param; Info tab uses AddressAutocomplete; save long_lat
gui/main_window.py               modify — pass google_api_key into wizard + member widget
tests/test_db_members.py             modify — INSERT_CONTACT/SET_LONG_LAT column tests
tests/test_db_members_integration.py modify — long_lat insert + set round-trip
tests/test_settings.py               modify — google_api_key default
tests/test_address_autocomplete.py   create — parse_place_location + no-key widget tests
```

`Long Lat` is stored as `"<lng>,<lat>"` (e.g. `-73.993455,40.695925`), matching existing data.

---

## Task 1: DB — Long Lat insert + set_member_long_lat

**Files:**
- Modify: `db/members.py`
- Test: `tests/test_db_members.py`, `tests/test_db_members_integration.py`

- [ ] **Step 1: Add the failing unit tests to `tests/test_db_members.py`**

```python
def test_insert_contact_includes_long_lat():
    from db.members import INSERT_CONTACT
    assert "[Long Lat]" in INSERT_CONTACT
    assert INSERT_CONTACT.count("?") == 6


def test_set_long_lat_targets_correct_columns():
    from db.members import SET_LONG_LAT
    assert "UPDATE [Contacts]" in SET_LONG_LAT
    assert "[Long Lat]=?" in SET_LONG_LAT
    assert "WHERE [Center ID]=?" in SET_LONG_LAT
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv\Scripts\pytest tests/test_db_members.py -k "long_lat" -v`
Expected: FAIL — `[Long Lat]` not present / `ImportError: cannot import name 'SET_LONG_LAT'`

- [ ] **Step 3: Add the failing integration test to the BOTTOM of `tests/test_db_members_integration.py`**

```python
def test_long_lat_insert_and_set_round_trip():
    from datetime import date
    from db.members import (
        insert_member, set_member_long_lat, center_id_exists, _connect,
        DELETE_ENROLLMENT,
    )
    import pyodbc

    cid = 880088  # implausible test id
    # ensure clean slate
    if center_id_exists(cid, TEST_DB):
        return  # don't clobber real data; skip
    insert_member(
        center_id=cid, last_name="LLTEST", first_name="Geo",
        health_plan="HF", address="12 Monroe St, New York, NY",
        enrollment_start=date(2026, 1, 1), enrollment_end=None,
        authorization=None, availability_rows=[],
        long_lat="-73.99,40.69", db_path=TEST_DB,
    )
    conn = _connect(TEST_DB)
    try:
        c = conn.cursor()
        c.execute("SELECT [Long Lat] FROM [Contacts] WHERE [Center ID]=?", cid)
        assert c.fetchone()[0] == "-73.99,40.69"
        set_member_long_lat(cid, "-74.00,40.70", TEST_DB)
        conn2 = _connect(TEST_DB)
        try:
            c2 = conn2.cursor()
            c2.execute("SELECT [Long Lat] FROM [Contacts] WHERE [Center ID]=?", cid)
            assert c2.fetchone()[0] == "-74.00,40.70"
        finally:
            conn2.close()
    finally:
        conn.close()
        # cleanup: delete the contact + its enrollment
        conn3 = _connect(TEST_DB)
        try:
            cc = conn3.cursor()
            cc.execute("DELETE FROM [Enrollment] WHERE [Center ID]=?", cid)
            cc.execute("DELETE FROM [Contacts] WHERE [Center ID]=?", cid)
            conn3.commit()
        finally:
            conn3.close()
```

- [ ] **Step 4: Run it to verify it fails**

Run: `.venv\Scripts\pytest tests/test_db_members_integration.py::test_long_lat_insert_and_set_round_trip -v`
Expected: FAIL — `insert_member() got an unexpected keyword argument 'long_lat'`

- [ ] **Step 5: Implement in `db/members.py`**

Replace the `INSERT_CONTACT` constant (currently near line 31):

```python
INSERT_CONTACT = (
    "INSERT INTO [Contacts] ([Center ID], [Last Name], [First Name], "
    "[Health Plan], [Address], [Long Lat]) VALUES (?, ?, ?, ?, ?, ?)"
)
```

Add this constant immediately after `INSERT_CONTACT`:

```python
SET_LONG_LAT = "UPDATE [Contacts] SET [Long Lat]=? WHERE [Center ID]=?"
```

In `insert_member`, add a `long_lat: str = ""` parameter (place it right before
`db_path: str`) and pass it in the `INSERT_CONTACT` execute. The signature
becomes:

```python
def insert_member(
    center_id: int,
    last_name: str,
    first_name: str,
    health_plan: str,
    address: str,
    enrollment_start: date,
    enrollment_end: date | None,
    authorization: dict | None,
    availability_rows: list[dict],
    long_lat: str = "",
    db_path: str = "",
) -> None:
```

and the contact insert line becomes:

```python
        c.execute(INSERT_CONTACT,
                  (center_id, last_name, first_name, health_plan, address, long_lat))
```

> Note: `db_path` gets a default only to keep it after the new keyword arg; all
> callers pass `db_path=...` by keyword, so this is safe.

Add this function right after `insert_member` (after its `finally: conn.close()`):

```python
def set_member_long_lat(center_id: int, long_lat: str, db_path: str) -> None:
    """Persist 'lng,lat' to a member's [Long Lat] (only when a place was picked)."""
    conn = _connect(db_path)
    try:
        conn.cursor().execute(SET_LONG_LAT, (long_lat, center_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

- [ ] **Step 6: Run both new tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_db_members.py -k "long_lat" tests/test_db_members_integration.py::test_long_lat_insert_and_set_round_trip -v`
Expected: 3 passed

- [ ] **Step 7: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add db/members.py tests/test_db_members.py tests/test_db_members_integration.py
git commit -m "feat: persist [Long Lat] on member insert + set_member_long_lat for edits"
```
End the commit message with the trailer:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: Settings — Google API key

**Files:**
- Modify: `settings.py`, `gui/settings_dialog.py`
- Test: `tests/test_settings.py`

- [ ] **Step 1: Add the failing settings test to `tests/test_settings.py`**

```python
def test_google_api_key_default_present(tmp_path):
    from settings import DEFAULT_SETTINGS
    path = tmp_path / "settings.json"
    result = load_settings(str(path))
    assert "google_api_key" in DEFAULT_SETTINGS
    assert result["google_api_key"] == ""
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv\Scripts\pytest tests/test_settings.py::test_google_api_key_default_present -v`
Expected: FAIL — `KeyError: 'google_api_key'`

- [ ] **Step 3: Add the default in `settings.py`**

In `DEFAULT_SETTINGS`, add the key:

```python
DEFAULT_SETTINGS = {
    "db_path": "",
    "theme": "dark",
    "events_db_path": "",
    "google_api_key": "",
}
```

- [ ] **Step 4: Run the settings test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_settings.py::test_google_api_key_default_present -v`
Expected: PASS

- [ ] **Step 5: Add the field to `gui/settings_dialog.py`**

In `_build_ui`, after the Events DB path row (`form.addRow("Events log path:", ev_row)`)
and before the Theme row, add:

```python
        # Google API key
        self._api_key = QLineEdit(self._settings.get("google_api_key", ""))
        self._api_key.setPlaceholderText("Google Maps Platform API key (Places API)")
        form.addRow("Google API key:", self._api_key)
```

In `result_settings`, add the key to the returned dict:

```python
    def result_settings(self) -> dict:
        return {
            "db_path": self._db_path.text().strip(),
            "events_db_path": self._events_path.text().strip(),
            "theme": "light" if self._radio_light.isChecked() else "dark",
            "google_api_key": self._api_key.text().strip(),
        }
```

- [ ] **Step 6: Add a dialog test to `tests/test_settings.py`**

```python
def test_settings_dialog_returns_google_api_key(qtbot):
    from gui.settings_dialog import SettingsDialog
    dlg = SettingsDialog({"db_path": "", "events_db_path": "", "theme": "dark",
                          "google_api_key": "KEY123"})
    qtbot.addWidget(dlg)
    assert dlg.result_settings()["google_api_key"] == "KEY123"
```

- [ ] **Step 7: Run the settings tests + full suite**

Run: `.venv\Scripts\pytest tests/test_settings.py -v`
Expected: all pass (incl. the two new tests).

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add settings.py gui/settings_dialog.py tests/test_settings.py
git commit -m "feat: add Google API key to settings + Settings dialog"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 3: parse_place_location pure helper

**Files:**
- Create: `gui/address_autocomplete.py`
- Test: `tests/test_address_autocomplete.py`

- [ ] **Step 1: Create `tests/test_address_autocomplete.py`**

```python
def test_parse_place_location_well_formed():
    from gui.address_autocomplete import parse_place_location
    details = {"result": {"geometry": {"location":
              {"lat": 40.695925, "lng": -73.993455}}}}
    assert parse_place_location(details) == "-73.993455,40.695925"


def test_parse_place_location_missing_returns_empty():
    from gui.address_autocomplete import parse_place_location
    assert parse_place_location({}) == ""
    assert parse_place_location({"result": {}}) == ""
    assert parse_place_location({"result": {"geometry": {}}}) == ""
    assert parse_place_location(None) == ""
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv\Scripts\pytest tests/test_address_autocomplete.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gui.address_autocomplete'`

- [ ] **Step 3: Create `gui/address_autocomplete.py` with the pure helper only**

```python
"""Google Places address autocomplete widget (native Qt, async via QtNetwork).

`parse_place_location` is pure and unit-tested. The widget (added below) degrades
to a plain text field when no API key is configured.
"""

AUTOCOMPLETE_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def parse_place_location(details_json) -> str:
    """Extract 'lng,lat' from a Place Details response, or '' if absent.

    Reads result.geometry.location.{lng,lat}. Never raises.
    """
    try:
        loc = details_json["result"]["geometry"]["location"]
        return f"{loc['lng']},{loc['lat']}"
    except (KeyError, TypeError):
        return ""
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_address_autocomplete.py -v`
Expected: 2 passed

- [ ] **Step 5: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add gui/address_autocomplete.py tests/test_address_autocomplete.py
git commit -m "feat: add parse_place_location helper for Places details"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 4: AddressAutocomplete widget

**Files:**
- Modify: `gui/address_autocomplete.py`
- Test: `tests/test_address_autocomplete.py`

- [ ] **Step 1: Add the failing widget test to `tests/test_address_autocomplete.py`**

```python
def test_no_key_is_plain_field(qtbot):
    from gui.address_autocomplete import AddressAutocomplete
    w = AddressAutocomplete("")
    qtbot.addWidget(w)
    w.set_address("123 Main St, New York, NY")
    assert w.text() == "123 Main St, New York, NY"
    assert w.address() == "123 Main St, New York, NY"
    assert w.long_lat() == ""
    assert w._popup is None  # no autocomplete machinery without a key


def test_setplaceholder_and_textchanged_proxy(qtbot):
    from gui.address_autocomplete import AddressAutocomplete
    w = AddressAutocomplete("")
    qtbot.addWidget(w)
    seen = []
    w.textChanged.connect(seen.append)
    w.setPlaceholderText("Street, City, State ZIP")
    w.setText("hello")
    assert seen == ["hello"]
    assert w.long_lat() == ""
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv\Scripts\pytest tests/test_address_autocomplete.py -k "key or proxy" -v`
Expected: FAIL — `ImportError: cannot import name 'AddressAutocomplete'`

- [ ] **Step 3: Append the widget to `gui/address_autocomplete.py`**

Add these imports at the top of the file (below the docstring, above the URL constants):

```python
import json
import uuid
from urllib.parse import urlencode

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QListWidget, QLabel
from PyQt6.QtCore import Qt, QTimer, QUrl, QPoint, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
```

Append the widget class at the END of the file:

```python
class AddressAutocomplete(QWidget):
    """Address field with Google Places autocomplete (async via QtNetwork).

    Drop-in-ish for a QLineEdit: text()/setText()/setPlaceholderText() and a
    textChanged(str) signal. When an API key is set, typing shows a suggestion
    popup; picking one fills the formatted address and captures long_lat
    ('lng,lat'). With no key, it is a plain line edit (graceful degradation).
    """
    textChanged = pyqtSignal(str)

    def __init__(self, api_key: str = "", parent=None):
        super().__init__(parent)
        self._api_key = api_key or ""
        self._long_lat = ""
        self._session = uuid.uuid4().hex
        self._predictions = []  # list of (description, place_id)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._edit = QLineEdit()
        self._edit.textChanged.connect(self.textChanged)  # proxy for dirty tracking
        layout.addWidget(self._edit)

        self._status = QLabel("")
        self._status.setStyleSheet("color:#3d9e6e; font-size:10px;")
        self._status.hide()
        layout.addWidget(self._status)

        if self._api_key:
            self._popup = QListWidget()
            self._popup.setWindowFlags(Qt.WindowType.Popup)
            self._popup.itemClicked.connect(self._on_pick)
            self._nam = QNetworkAccessManager(self)
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.setInterval(300)
            self._timer.timeout.connect(self._request_predictions)
            self._edit.textEdited.connect(self._on_typed)
        else:
            self._popup = None

    # ── QLineEdit-ish API ─────────────────────────────────────────────────
    def text(self) -> str:
        return self._edit.text()

    def address(self) -> str:
        return self._edit.text()

    def setText(self, text: str) -> None:
        self._edit.setText(text)

    def set_address(self, text: str) -> None:
        self._edit.setText(text)

    def setPlaceholderText(self, text: str) -> None:
        self._edit.setPlaceholderText(text)

    def long_lat(self) -> str:
        return self._long_lat

    # ── typing → debounced autocomplete ───────────────────────────────────
    def _on_typed(self, _text: str):
        self._long_lat = ""        # editing invalidates a prior pick
        self._status.hide()
        self._timer.start()

    def _request_predictions(self):
        text = self._edit.text().strip()
        if len(text) < 3:
            self._popup.hide()
            return
        params = urlencode({
            "input": text, "key": self._api_key, "sessiontoken": self._session,
            "components": "country:us", "types": "address",
        })
        reply = self._nam.get(QNetworkRequest(QUrl(f"{AUTOCOMPLETE_URL}?{params}")))
        reply.finished.connect(lambda r=reply: self._on_predictions(r))

    def _on_predictions(self, reply):
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
        except Exception:
            data = {}
        finally:
            reply.deleteLater()
        self._predictions = [
            (p.get("description", ""), p.get("place_id", ""))
            for p in data.get("predictions", [])
        ][:5]
        if not self._predictions:
            self._popup.hide()
            return
        self._popup.clear()
        for desc, _pid in self._predictions:
            self._popup.addItem(desc)
        pos = self._edit.mapToGlobal(QPoint(0, self._edit.height()))
        self._popup.move(pos)
        self._popup.setFixedWidth(self._edit.width())
        self._popup.show()

    def _on_pick(self, _item):
        idx = self._popup.currentRow()
        if idx < 0 or idx >= len(self._predictions):
            return
        desc, place_id = self._predictions[idx]
        self._popup.hide()
        self._edit.setText(desc)   # programmatic -> no _on_typed, no lookup
        self._request_details(place_id)

    def _request_details(self, place_id: str):
        params = urlencode({
            "place_id": place_id, "key": self._api_key,
            "sessiontoken": self._session, "fields": "geometry/location",
        })
        reply = self._nam.get(QNetworkRequest(QUrl(f"{DETAILS_URL}?{params}")))
        reply.finished.connect(lambda r=reply: self._on_details(r))

    def _on_details(self, reply):
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
        except Exception:
            data = {}
        finally:
            reply.deleteLater()
        self._long_lat = parse_place_location(data)
        if self._long_lat:
            self._status.setText("📍 coordinates captured")
            self._status.show()
        self._session = uuid.uuid4().hex  # rotate token after a completed session
```

- [ ] **Step 4: Run the widget tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_address_autocomplete.py -v`
Expected: 4 passed

- [ ] **Step 5: Verify the module imports**

Run: `.venv\Scripts\python -c "from gui.address_autocomplete import AddressAutocomplete; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add gui/address_autocomplete.py tests/test_address_autocomplete.py
git commit -m "feat: AddressAutocomplete widget (Places autocomplete via QtNetwork)"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 5: Wizard integration

**Files:**
- Modify: `gui/wizard/step_contact.py`, `gui/wizard/wizard.py`, `gui/main_window.py`

- [ ] **Step 1: Use AddressAutocomplete in `gui/wizard/step_contact.py`**

Change the top import block to add the widget:

```python
from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QComboBox, QLabel, QVBoxLayout,
)
from db.members import HEALTH_PLANS
from gui.address_autocomplete import AddressAutocomplete
```

Change `__init__` to accept the api key:

```python
    def __init__(self, api_key: str = "", parent=None):
        super().__init__(parent)
        self._api_key = api_key or ""
        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #d05555; font-size: 11px;")
        self._build()
```

In `_build`, replace the address line:

```python
        self.address = QLineEdit()
        self.address.setPlaceholderText("Street, City, State ZIP")
```

with:

```python
        self.address = AddressAutocomplete(self._api_key)
        self.address.setPlaceholderText("Street, City, State ZIP")
```

In `collect`, add `long_lat`:

```python
    def collect(self) -> dict:
        return {
            "first_name": self.first_name.text().strip(),
            "last_name": self.last_name.text().strip(),
            "center_id": int(self.center_id.text().strip()),
            "health_plan": self.health_plan.currentText(),
            "address": self.address.text().strip(),
            "long_lat": self.address.long_lat(),
        }
```

- [ ] **Step 2: Thread the api key through `gui/wizard/wizard.py`**

Change `AddMemberWizard.__init__` to accept and store the key:

```python
    def __init__(self, db_path: str, events_path: str, api_key: str = "", parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._events_path = events_path
        self._api_key = api_key or ""
        self.setWindowTitle("Add New Member")
        self.setMinimumSize(700, 640)
        self._current = 0
        self._build_ui()
```

In `_build_ui`, pass the key to StepContact:

```python
        self._step_contact = StepContact(self._api_key)
```

In `_save`, pass `long_lat` to `insert_member` (add the one kwarg):

```python
            insert_member(
                center_id=c["center_id"],
                last_name=c["last_name"],
                first_name=c["first_name"],
                health_plan=c["health_plan"],
                address=c["address"],
                enrollment_start=data["enrollment_start"],
                enrollment_end=data["enrollment_end"],
                authorization=data.get("authorization"),
                availability_rows=data.get("availability_rows", []),
                long_lat=c.get("long_lat", ""),
                db_path=self._db_path,
            )
```

- [ ] **Step 3: Pass the key from `gui/main_window.py::_open_wizard`**

Find the wizard construction in `_open_wizard`:

```python
        from gui.wizard.wizard import AddMemberWizard
        events_path = self._settings.get("events_db_path", "")
        dlg = AddMemberWizard(db_path, events_path, self)
```

Replace with:

```python
        from gui.wizard.wizard import AddMemberWizard
        events_path = self._settings.get("events_db_path", "")
        api_key = self._settings.get("google_api_key", "")
        dlg = AddMemberWizard(db_path, events_path, api_key, self)
```

- [ ] **Step 4: Verify imports**

Run: `.venv\Scripts\python -c "from gui.wizard.wizard import AddMemberWizard; from gui.wizard.step_contact import StepContact; from gui.main_window import MainWindow; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Run the full suite (unaffected)**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add gui/wizard/step_contact.py gui/wizard/wizard.py gui/main_window.py
git commit -m "feat: wizard address autocomplete + persist long_lat on new member"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 6: Info tab integration

**Files:**
- Modify: `gui/member_tabs.py`, `gui/main_window.py`

- [ ] **Step 1: Add an `api_key` param to `MemberTabsWidget.__init__`**

Change the constructor signature + store the key. Find:

```python
    def __init__(self, center_id: int, db_path: str, events_path: str, parent=None):
        super().__init__(parent)
        self._center_id = center_id
        self._db_path = db_path
        self._events_path = events_path
        self._member = None
```

Replace with:

```python
    def __init__(self, center_id: int, db_path: str, events_path: str,
                 api_key: str = "", parent=None):
        super().__init__(parent)
        self._center_id = center_id
        self._db_path = db_path
        self._events_path = events_path
        self._api_key = api_key or ""
        self._member = None
```

- [ ] **Step 2: Pass the key from `gui/main_window.py::_show_member`**

Find:

```python
    def _show_member(self, center_id: int):
        from gui.member_tabs import MemberTabsWidget
        db_path = self._settings.get("db_path", "")
        events_path = self._settings.get("events_db_path", "")
        widget = MemberTabsWidget(center_id, db_path, events_path)
        self._set_detail(widget)
```

Replace with:

```python
    def _show_member(self, center_id: int):
        from gui.member_tabs import MemberTabsWidget
        db_path = self._settings.get("db_path", "")
        events_path = self._settings.get("events_db_path", "")
        api_key = self._settings.get("google_api_key", "")
        widget = MemberTabsWidget(center_id, db_path, events_path, api_key)
        self._set_detail(widget)
```

- [ ] **Step 3: Use AddressAutocomplete for the address in `_make_info_tab`**

In `_make_info_tab`, the Contact group currently builds the address via:

```python
        self._info_address   = field("address")
```

Replace that single line with:

```python
        from gui.address_autocomplete import AddressAutocomplete
        self._info_address = AddressAutocomplete(self._api_key)
        self._info_address.set_address(m.get("address", "") or "")
```

(The rest of the Contact group — `addRow("Address", self._info_address)` — is
unchanged; `AddressAutocomplete` is a `QWidget` and lays out fine in the form.)

- [ ] **Step 4: Persist long_lat in `_save_info` after a successful save**

In `_save_info`, find the success block right after the `update_contact(...)`
call where it does `self._member.update(fields)`:

```python
            self._member.update(fields)
            self._dirty = False
```

Replace with:

```python
            self._member.update(fields)
            self._dirty = False
            new_long_lat = self._info_address.long_lat()
            if new_long_lat:
                from db.members import set_member_long_lat
                set_member_long_lat(self._center_id, new_long_lat, self._db_path)
```

(`self._info_address.text()` in the `fields` dict and `set_address`/`setText`
in `_discard_info` and the `textChanged` connection in `_setup_dirty_tracking`
all keep working — `AddressAutocomplete` exposes those.)

- [ ] **Step 5: Verify imports**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; from gui.main_window import MainWindow; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Run the full suite (unaffected)**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add gui/member_tabs.py gui/main_window.py
git commit -m "feat: Info tab address autocomplete + persist long_lat on edit"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 7: Full suite + exe rebuild + manual smoke test

**Files:** none changed

- [ ] **Step 1: Run the full test suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass (prior 82 + the new long_lat, settings, and address-autocomplete tests).

- [ ] **Step 2: Rebuild the exe**

Stop any running instance (it locks the output file), then build:

```
powershell -Command "try { Stop-Process -Name MemberManager -Force -ErrorAction Stop } catch {}"
.venv\Scripts\pyinstaller MemberManager.spec
```

Expected: `Build complete! The results are available in: ...\dist`

- [ ] **Step 3: Manual smoke test**

Launch `dist\MemberManager.exe`:
- **No key set:** the address fields (wizard + Info tab) behave as plain text boxes; add/edit/save all work and leave `Long Lat` untouched.
- **With a key** (Settings → Google API key): in **Add New Member**, typing a
  partial address shows a suggestion dropdown; selecting one fills the formatted
  address and shows "📍 coordinates captured"; creating the member stores
  `Long Lat` (verify in the DB).
- In the **Info tab**, editing the address and picking a suggestion, then
  **Save Changes**, persists `Long Lat`; saving without re-picking leaves the
  existing `Long Lat` unchanged.

---

## Self-Review Notes

- **Spec coverage:** Settings key → Task 2. `parse_place_location` → Task 3.
  `AddressAutocomplete` widget (async QtNetwork, debounce, session token, US
  bias, graceful degradation) → Task 4. Wizard integration + new-member insert
  with `[Long Lat]` → Tasks 1 (DB) + 5 (UI). Info-tab integration + edit-path
  `set_member_long_lat` (only when picked) → Tasks 1 (DB) + 6 (UI). Testing →
  Tasks 1–4 (unit/integration) + Task 7 (full run + manual).
- **Type consistency:** `parse_place_location(details_json) -> str`,
  `AddressAutocomplete(api_key="")` with `text()/address()/setText()/set_address()/`
  `setPlaceholderText()/long_lat()` + `textChanged(str)`, `insert_member(...,
  long_lat="", db_path="")`, `set_member_long_lat(center_id, long_lat, db_path)`,
  `INSERT_CONTACT` (6 placeholders), `SET_LONG_LAT`, `AddMemberWizard(db_path,
  events_path, api_key="", parent)`, `StepContact(api_key="")`,
  `MemberTabsWidget(center_id, db_path, events_path, api_key="", parent)` are used
  consistently across tasks.
- **No placeholders:** every code step is complete; commands list expected output.
- **Note:** `Long Lat` is written as `"<lng>,<lat>"`; coords are captured only on
  a picked suggestion; `update_contact`/`UPDATE_CONTACT` are never modified, so a
  normal edit save never clobbers existing coordinates.
