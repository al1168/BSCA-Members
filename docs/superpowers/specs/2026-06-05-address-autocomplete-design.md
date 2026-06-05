# Google Places Address Autocomplete + Lat/Long Capture — Design Spec

**Date:** 2026-06-05
**Status:** Approved (pending spec review)

## Goal

Give the member **address** field Google Places autocomplete in both the
**Add New Member** wizard and the **Edit member** (Info tab). When the user
picks a suggestion, capture its coordinates and persist them to the existing
`[Long Lat]` column of the `Contacts` table (format `longitude,latitude`).

## Decisions (from brainstorming)

- **API key**: stored in the app's settings JSON (`google_api_key`), entered via
  the Settings dialog. Blank key (or any failure) → graceful degradation to a
  plain text field.
- **Coordinates**: captured **only** when the user selects a dropdown
  suggestion. Free-typed text never geocodes. On edit, `Long Lat` is left
  unchanged unless a new suggestion is picked.
- **HTTP**: Qt's `QNetworkAccessManager` (ships with PyQt6 — async, non-blocking,
  **no new dependency**). No `requests`, no threads, no WebEngine.
- **`Long Lat` format**: `"<lng>,<lat>"` (e.g. `-73.993455,40.695925`), matching
  existing data.

## Architecture

- A reusable widget `gui/address_autocomplete.py::AddressAutocomplete` owns a
  `QLineEdit`, a popup suggestion list, a `QNetworkAccessManager`, a debounce
  timer, and a per-session token. It reads the API key from settings. A pure
  helper `parse_place_location(details_json) -> str` is unit-tested.
- The wizard's `StepContact` and the Info tab use the widget in place of the
  plain address `QLineEdit`.
- `db/members.py` gains `[Long Lat]` in `INSERT_CONTACT` (new members) and a
  small isolated `set_member_long_lat(center_id, long_lat, db_path)` for the
  edit path. `update_contact` is unchanged.

## Tech Stack

Python 3.11, PyQt6 (incl. `PyQt6.QtNetwork`, already bundled), pyodbc, pytest.
**No new dependencies.** Google Maps Platform: Places API (Autocomplete + Place
Details).

---

## Settings

`settings.py` `DEFAULT_SETTINGS` gains `"google_api_key": ""`. The Settings
dialog (`gui/settings_dialog.py`) gains a "Google API key" `QLineEdit` row
(echo normal text; it's a server key, not a password) wired into
`result_settings()`. `MainWindow` already persists settings on dialog accept.

The key is passed to each `AddressAutocomplete` at construction
(`self._settings.get("google_api_key", "")`). Operational note (docs only, not
code): restrict the key to the Places API in the Google Cloud console.

## `AddressAutocomplete` widget (`gui/address_autocomplete.py`, new)

A `QWidget` exposing the same surface the address field needs, so call sites
change minimally.

**Construction:** `AddressAutocomplete(api_key: str, parent=None)`.

**Composition:**
- `QLineEdit` (street-address placeholder).
- A frameless popup `QListWidget` anchored under the line edit, showing up to ~5
  suggestion descriptions. Hidden when empty / on focus-out / on selection.
- A small status `QLabel` (e.g. `📍 coordinates captured`) shown only after a
  pick.
- `QNetworkAccessManager` for async calls; a `QTimer` (single-shot, ~300 ms) to
  debounce keystrokes; a session-token string (uuid4) regenerated after each
  completed selection.

**Public API:**
- `text() -> str` / `address() -> str` — current line-edit text.
- `set_address(text: str) -> None` — seed the field (used when editing); does
  **not** trigger a lookup and does **not** set coordinates.
- `long_lat() -> str` — the captured `"lng,lat"` for a suggestion picked this
  session, else `""`.
- `setPlaceholderText(...)` passthrough.

**Behavior:**
- On `textEdited` (user typing, not programmatic `set_address`): restart the
  debounce timer; clear any previously captured `long_lat` (typing invalidates a
  prior pick). When the timer fires and the text is ≥ 3 chars and a key is
  present, issue an **Autocomplete** request (US-biased, session token).
- On Autocomplete response: populate the popup with predictions
  (`description` + `place_id`). Network/JSON errors or no key → hide the popup
  silently (field still usable).
- On selecting a prediction: issue a **Place Details** request for that
  `place_id` (location field only). On response, set the line edit to the
  formatted address via `set_address`, set `long_lat` from
  `parse_place_location(...)`, show the status label, hide the popup, and rotate
  the session token.
- If `api_key` is empty: behaves as a plain line edit (no timer, no popup, no
  status). This is the graceful-degradation path.

**Google endpoints (Places API):**
- Autocomplete: `https://maps.googleapis.com/maps/api/place/autocomplete/json`
  with query params `input`, `key`, `sessiontoken`, `components=country:us`,
  `types=address`.
- Place Details: `https://maps.googleapis.com/maps/api/place/details/json`
  with `place_id`, `key`, `sessiontoken`, `fields=geometry/location`.
  (Legacy Places endpoints; simple GET + JSON. If migrated to Places API (New)
  later, only this widget changes.)

**Pure helper (unit-tested):**

```python
def parse_place_location(details_json: dict) -> str:
    """Extract 'lng,lat' from a Place Details response, or '' if absent.

    Reads result.geometry.location.{lng,lat}. Returns e.g. '-73.993455,40.695925'.
    Any missing key / wrong shape -> '' (never raises).
    """
```

## Wizard integration (`gui/wizard/step_contact.py`)

- Replace `self.address = QLineEdit()` with
  `self.address = AddressAutocomplete(api_key)`, where `api_key` comes from the
  wizard's settings (thread the key from `MainWindow` → `AddMemberWizard` →
  `StepContact`; the wizard is constructed in `MainWindow._open_wizard`).
- `collect()` returns the existing keys **plus** `"long_lat": self.address.long_lat()`.
- `validate()` is unchanged (address stays optional).

## New-member insert (`db/members.py`)

- Extend `INSERT_CONTACT` to include `[Long Lat]`:
  `INSERT INTO [Contacts] ([Center ID],[Last Name],[First Name],[Health Plan],[Address],[Long Lat]) VALUES (?,?,?,?,?,?)`.
- `insert_member(...)` gains a `long_lat: str = ""` parameter (kept backward
  compatible) and binds it. The wizard's save path passes
  `collect()["long_lat"]`.

## Info tab integration (`gui/member_tabs.py`)

- In `_make_info_tab`, replace the address `QLineEdit` with
  `AddressAutocomplete(self._api_key)` (the widget is given the api key, which
  `MemberTabsWidget` receives from `MainWindow._show_member`), seeded via
  `set_address(m.get("address",""))`.
- Dirty tracking: connect the widget's inner line edit `textChanged` to the
  existing dirty flag (the widget exposes the signal or a `textChanged` of its
  own).
- In `_save_info`: read `self._info_address.address()` for the address field as
  today (it flows through `build_change_summary` and `update_contact`
  unchanged). **After** a successful `update_contact`, if
  `self._info_address.long_lat()` is non-empty, call
  `set_member_long_lat(self._center_id, long_lat, self._db_path)`. If empty,
  leave `[Long Lat]` untouched.

## Edit-path DB write (`db/members.py`)

```python
SET_LONG_LAT = "UPDATE [Contacts] SET [Long Lat]=? WHERE [Center ID]=?"

def set_member_long_lat(center_id: int, long_lat: str, db_path: str) -> None:
    """Persist 'lng,lat' to the member's [Long Lat] (only called when a
    suggestion was picked)."""
    # _connect → execute(SET_LONG_LAT, (long_lat, center_id)) → commit
    # except rollback+raise / finally close  (same pattern as other writers)
```

`update_contact` and `UPDATE_CONTACT` are **not** modified, so a normal save of
a member whose address wasn't re-selected never overwrites existing coordinates.

## Threading / responsiveness

`QNetworkAccessManager` is asynchronous and runs on the GUI event loop, so
typing stays responsive without worker threads. Debounce limits request volume;
session tokens keep Autocomplete + the closing Details call billed as one
session.

## Testing

### Unit tests (`tests/test_address_autocomplete.py`, new)
- `parse_place_location` returns `"-73.993455,40.695925"` for a well-formed
  Place Details dict.
- `parse_place_location` returns `""` for `{}`, for missing `geometry`, and for
  missing `location` — never raises.
- Constructing `AddressAutocomplete("")` (no key) leaves the widget in
  plain-field mode: `long_lat()` is `""` and no popup is created on `set_address`.
  (Run under `QT_QPA_PLATFORM=offscreen`.)

### Unit test (`tests/test_db_members.py`)
- `INSERT_CONTACT` contains `[Long Lat]` and has 6 `?` placeholders.
- `SET_LONG_LAT` targets `[Long Lat]` and `WHERE [Center ID]=?`.

### Integration test (`tests/test_db_members_integration.py`)
- Insert a member with `insert_member(..., long_lat="-73.99,40.69")`; read the
  row back and assert `[Long Lat]` persisted; then `set_member_long_lat` to a new
  value and confirm the update; clean up (delete the contact row) in `finally`.

### Manual verification
- With a valid key: typing a partial address shows suggestions; selecting one
  fills the formatted address and shows "coordinates captured"; saving persists
  `Long Lat` (verify in the DB). In the wizard, adding a member with a picked
  address stores `Long Lat`.
- With a blank key: the address field is a plain box; add/edit/save all work and
  leave `Long Lat` untouched.

## Out of scope

- Geocoding free-typed addresses (coords only from a picked suggestion).
- Map preview, reverse geocoding, or hand-editing `Long Lat`.
- Backfilling coordinates for existing members.
- Migrating to the Places API (New); the legacy endpoints are isolated in the
  widget and can be swapped later without touching call sites.
