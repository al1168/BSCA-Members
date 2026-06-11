# Profile Photo Add/Replace — Design Spec

**Date:** 2026-06-09
**Status:** Approved (pending spec review)

## Goal

Let staff set or replace a member's profile photo by clicking the photo in the
header, choosing an image file, and storing it in the Access `Contacts.Photo`
attachment field. Replacing an existing photo asks for confirmation first.

## Background (current state)

- Photos are stored in an Access **Attachment** field named `Photo` on the
  `Contacts` table. They are **read** via DAO/win32com in
  `db.members.get_member_photo(center_id, db_path)`, which reads the child
  recordset's `FileData` and returns the JPEG bytes starting at the first
  `FF D8 FF` marker (Access prepends attachment metadata). The read path therefore
  assumes **JPEG**.
- `db/members.py` has DAO helpers: `_dao_database(db_path)` returns a **cached,
  read-only, shared** DAO handle; `_drop_dao_database(db_path)` closes/forgets it.
  Attachment fields are not writable via pyodbc.
- `gui/member_tabs.py` `_make_photo_label` returns a plain 80×80 `QLabel` showing
  the photo (cropped to a circle-ish square) or a drawn placeholder. It is built in
  `_build_ui`'s header and is **not** clickable.
- The widget already has `_log_event(event_type, description)` for the audit log.

## Architecture

### 1. DB write — `set_member_photo(center_id, image_path, db_path)` (`db/members.py`)

Writes `image_path` (a JPEG file) into the member's `Photo` attachment, replacing
any existing attachment. Uses DAO with a **fresh writable handle** (the cached one
is read-only):

```python
def set_member_photo(center_id: int, image_path: str, db_path: str) -> None:
    import win32com.client
    engine = win32com.client.Dispatch("DAO.DBEngine.120")
    db = engine.OpenDatabase(db_path, False, False)  # shared, read-write
    try:
        rs = db.OpenRecordset(
            f"SELECT * FROM [Contacts] WHERE [Center ID]={int(center_id)}"
        )
        if rs.EOF:
            rs.Close()
            raise ValueError(f"No contact with Center ID {center_id}")
        rs.Edit()
        child = rs.Fields("Photo").Value          # attachment child recordset
        while not child.EOF:                      # clear existing attachment(s)
            child.Delete()
            child.MoveNext()
        child.AddNew()
        child.Fields("FileData").LoadFromFile(image_path)
        child.Update()
        rs.Update()
        rs.Close()
    finally:
        db.Close()
    # Next get_member_photo must reopen so it sees the new image.
    _drop_dao_database(db_path)
```

Notes: opening a fresh writable handle avoids disturbing the cached read-only one;
shared mode coexists with the pyodbc read connection. Any DAO error propagates to
the caller. `LoadFromFile` sets the attachment file name from the path basename;
deleting existing rows first avoids duplicate-name conflicts.

### 2. Image normalization — `to_jpeg_bytes(src_path)` (`gui/member_tabs.py`)

Because the read path only understands JPEG, any chosen image is re-encoded to
JPEG before storage:

```python
def to_jpeg_bytes(src_path: str) -> bytes:
    """Load an image file and return JPEG-encoded bytes. Raises ValueError if the
    file can't be read as an image."""
    from PyQt6.QtGui import QImage
    from PyQt6.QtCore import QBuffer, QByteArray
    img = QImage(src_path)
    if img.isNull():
        raise ValueError("Could not read the selected image.")
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    img.save(buf, "JPEG", 90)
    buf.close()
    return bytes(ba)
```

### 3. Clickable photo + change flow (`gui/member_tabs.py`)

- `_PhotoLabel(QLabel)`: a small subclass exposing a `clicked` signal
  (`pyqtSignal()`), with `setCursor(Qt.CursorShape.PointingHandCursor)` and tooltip
  "Click to change photo"; `mousePressEvent` emits `clicked` (left button) then
  calls `super().mousePressEvent(e)`.
- `_make_photo_label` builds `self._photo_label = _PhotoLabel(...)`, sets its
  pixmap (existing logic), records `self._has_photo = bool(photo_bytes)`, and
  connects `self._photo_label.clicked.connect(self._change_photo)`. Refactor the
  pixmap-setting (photo vs placeholder) into a helper `self._set_photo_pixmap(
  photo_bytes)` reused by build and reload.
- `_change_photo(self)`:
  1. If `self._has_photo`, `QMessageBox.question(... "Replace existing photo?")`;
     return on No.
  2. `path, _ = QFileDialog.getOpenFileName(self, "Choose photo", "",
     "Images (*.jpg *.jpeg *.png *.bmp *.webp)")`; return if empty.
  3. `data = to_jpeg_bytes(path)` (on `ValueError` → `QMessageBox.critical`, return).
  4. Write `data` to a `tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)`,
     close it, then `set_member_photo(self._center_id, tmp_path, self._db_path)` in
     a try/except (`QMessageBox.critical` on failure); always remove the temp file.
  5. On success: `self._set_photo_pixmap(get_member_photo(self._center_id,
     self._db_path))`, `self._has_photo = True`, and `self._log_event("EDIT",
     "Photo updated")`.

## Data flow

Click → confirm (if replacing) → file pick → `to_jpeg_bytes` → temp `.jpg` →
`set_member_photo` (DAO write, drop cached read handle) → reload pixmap via
`get_member_photo` → audit log.

## Error handling / edge cases

- Unreadable/corrupt image → `to_jpeg_bytes` raises → "Could not read the selected
  image." No write.
- No contact row for the id → `set_member_photo` raises `ValueError` → surfaced.
- DB locked / exclusive / DAO failure → exception surfaced via `QMessageBox.critical`.
- Cancelled file dialog or declined confirmation → no-op.
- Temp file is always cleaned up (in a `finally`).
- Non-JPEG inputs (PNG/BMP/WebP) are normalized to JPEG so the existing read path
  displays them.

## Testing

- `to_jpeg_bytes` (offscreen Qt): generate a small PNG (e.g. a filled `QImage`
  saved to a temp `.png`), call `to_jpeg_bytes` on it, assert the result is
  non-empty and starts with `b"\xff\xd8\xff"` (valid JPEG); a non-image file raises
  `ValueError`.
- The DAO write (`set_member_photo`) and the full click flow are verified manually
  (they require Access + win32com + a writable DB).
- Then full suite, exe rebuild, and a manual check: clicking a member's photo opens
  a file picker; choosing an image saves it and shows it immediately; replacing an
  existing photo prompts to confirm; reopening the member still shows the new photo;
  the Events log shows "Photo updated".

## Out of scope

- Removing a photo, cropping/rotating/editing, or multiple photos per member.
- Changing how photos are read (`get_member_photo` is unchanged).
