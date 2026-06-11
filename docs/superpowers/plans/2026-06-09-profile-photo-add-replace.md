# Profile Photo Add/Replace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Click a member's header photo to choose an image and store it in the Access `Contacts.Photo` attachment field (replacing an existing one after a confirmation).

**Architecture:** A DAO writable-handle function `set_member_photo` in `db/members.py`; a `to_jpeg_bytes` normalizer + a clickable `_PhotoLabel` + a `_change_photo` flow in `gui/member_tabs.py`. The existing `get_member_photo` (DAO read, JPEG-only) is unchanged, so chosen images are re-encoded to JPEG before storage.

**Tech Stack:** Python 3.11, PyQt6, pywin32 (DAO), Access, pytest. No new dependencies.

---

## File Map

```
db/members.py            modify — set_member_photo (DAO write)
gui/member_tabs.py       modify — to_jpeg_bytes, _PhotoLabel, _change_photo,
                                  _set_photo_pixmap; refactor _make_photo_label
tests/test_photo.py      create — to_jpeg_bytes unit tests
```

---

## Task 1: DB write — `set_member_photo` (`db/members.py`)

**Files:**
- Modify: `db/members.py`

- [ ] **Step 1: Add the function**

In `db/members.py`, add after `get_member_photo` (it ends around line 332). Access
Attachment fields aren't writable via pyodbc, so this uses a fresh **writable** DAO
handle (the cached `_dao_database` handle is read-only):

```python
def set_member_photo(center_id: int, image_path: str, db_path: str) -> None:
    """Store image_path (a JPEG file) in the member's Contacts.Photo attachment,
    replacing any existing attachment. Uses a fresh writable DAO handle."""
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
    # Drop the cached read-only handle so the next get_member_photo reads fresh.
    _drop_dao_database(db_path)
```

(`_drop_dao_database` already exists in this file.)

- [ ] **Step 2: Verify it imports**

Run: `.venv\Scripts\python -c "from db.members import set_member_photo; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Run the full suite (nothing should break)**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add db/members.py
git commit -m "feat: set_member_photo writes a photo to the Access attachment field"
```
End the commit message with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: Image normalizer — `to_jpeg_bytes` (TDD)

**Files:**
- Create: `tests/test_photo.py`
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_photo.py`:

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_to_jpeg_bytes_from_png(qapp, tmp_path):
    from PyQt6.QtGui import QImage
    from gui.member_tabs import to_jpeg_bytes
    png = tmp_path / "x.png"
    img = QImage(10, 10, QImage.Format.Format_RGB32)
    img.fill(0xFF8800)
    assert img.save(str(png), "PNG")
    data = to_jpeg_bytes(str(png))
    assert len(data) > 0
    assert data[:3] == b"\xff\xd8\xff"


def test_to_jpeg_bytes_invalid_raises(qapp, tmp_path):
    from gui.member_tabs import to_jpeg_bytes
    bad = tmp_path / "x.txt"
    bad.write_text("not an image")
    with pytest.raises(ValueError):
        to_jpeg_bytes(str(bad))
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv\Scripts\pytest tests/test_photo.py -v`
Expected: FAIL (`cannot import name 'to_jpeg_bytes'`).

- [ ] **Step 3: Implement `to_jpeg_bytes`**

In `gui/member_tabs.py`, add this module-level function among the other module-level
helpers (e.g. after `build_change_summary`, before `class MemberTabsWidget`):

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

- [ ] **Step 4: Run to verify they pass**

Run: `.venv\Scripts\pytest tests/test_photo.py -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add gui/member_tabs.py tests/test_photo.py
git commit -m "feat: add to_jpeg_bytes image normalizer for profile photos"
```
End with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 3: Clickable photo + change flow (`gui/member_tabs.py`)

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Add `pyqtSignal` to the QtCore import**

The current import (line 5) is:

```python
from PyQt6.QtCore import Qt
```

Replace with:

```python
from PyQt6.QtCore import Qt, pyqtSignal
```

- [ ] **Step 2: Add the `_PhotoLabel` class**

In `gui/member_tabs.py`, add at module scope (near the other module-level classes,
e.g. just before `class MemberTabsWidget`):

```python
class _PhotoLabel(QLabel):
    """An 80x80 photo label that emits `clicked` when pressed (left button)."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to change photo")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)
```

- [ ] **Step 3: Refactor `_make_photo_label` + add `_set_photo_pixmap`**

The current method is:

```python
    def _make_photo_label(self) -> QLabel:
        """Return an 80×80 QLabel showing the member photo or a gray placeholder."""
        from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush
        from PyQt6.QtCore import Qt as QtCore
        from db.members import get_member_photo

        lbl = QLabel()
        lbl.setFixedSize(80, 80)
        lbl.setStyleSheet("border-radius: 40px; overflow: hidden;")

        photo_bytes = get_member_photo(self._center_id, self._db_path)
        if photo_bytes:
            pix = QPixmap()
            pix.loadFromData(photo_bytes)
            pix = pix.scaled(80, 80, QtCore.AspectRatioMode.KeepAspectRatioByExpanding,
                             QtCore.TransformationMode.SmoothTransformation)
            if pix.width() > 80 or pix.height() > 80:
                x = (pix.width() - 80) // 2
                y = (pix.height() - 80) // 2
                pix = pix.copy(x, y, 80, 80)
            lbl.setPixmap(pix)
        else:
            pix = QPixmap(80, 80)
            pix.fill(QtCore.GlobalColor.transparent)
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QBrush(QColor("#3a3a3a")))
            painter.setPen(QtCore.PenStyle.NoPen)
            painter.drawEllipse(0, 0, 80, 80)
            painter.setBrush(QBrush(QColor("#888888")))
            painter.drawEllipse(28, 12, 24, 24)
            painter.drawEllipse(12, 46, 56, 40)
            painter.end()
            lbl.setPixmap(pix)

        return lbl
```

Replace it with these two methods:

```python
    def _make_photo_label(self) -> QLabel:
        """Return an 80×80 clickable label showing the member photo. Clicking it
        opens a file picker to set/replace the photo."""
        from db.members import get_member_photo
        self._photo_label = _PhotoLabel()
        self._photo_label.setFixedSize(80, 80)
        self._photo_label.setStyleSheet("border-radius: 40px; overflow: hidden;")
        self._photo_label.clicked.connect(self._change_photo)
        self._set_photo_pixmap(get_member_photo(self._center_id, self._db_path))
        return self._photo_label

    def _set_photo_pixmap(self, photo_bytes):
        """Paint the member photo (or the placeholder) onto self._photo_label and
        record whether a photo exists."""
        from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush
        from PyQt6.QtCore import Qt as QtCore
        self._has_photo = bool(photo_bytes)
        if photo_bytes:
            pix = QPixmap()
            pix.loadFromData(photo_bytes)
            pix = pix.scaled(80, 80, QtCore.AspectRatioMode.KeepAspectRatioByExpanding,
                             QtCore.TransformationMode.SmoothTransformation)
            if pix.width() > 80 or pix.height() > 80:
                x = (pix.width() - 80) // 2
                y = (pix.height() - 80) // 2
                pix = pix.copy(x, y, 80, 80)
            self._photo_label.setPixmap(pix)
        else:
            pix = QPixmap(80, 80)
            pix.fill(QtCore.GlobalColor.transparent)
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QBrush(QColor("#3a3a3a")))
            painter.setPen(QtCore.PenStyle.NoPen)
            painter.drawEllipse(0, 0, 80, 80)
            painter.setBrush(QBrush(QColor("#888888")))
            painter.drawEllipse(28, 12, 24, 24)
            painter.drawEllipse(12, 46, 56, 40)
            painter.end()
            self._photo_label.setPixmap(pix)
```

- [ ] **Step 4: Add `_change_photo`**

Add this method to `MemberTabsWidget` (e.g. right after `_set_photo_pixmap`):

```python
    def _change_photo(self):
        from PyQt6.QtWidgets import QFileDialog
        from db.members import set_member_photo, get_member_photo
        import os
        import tempfile

        if self._has_photo:
            if QMessageBox.question(
                self, "Replace photo",
                "Replace this member's existing photo?",
            ) != QMessageBox.StandardButton.Yes:
                return

        path, _ = QFileDialog.getOpenFileName(
            self, "Choose photo", "",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp)",
        )
        if not path:
            return

        try:
            data = to_jpeg_bytes(path)
        except ValueError as exc:
            QMessageBox.critical(self, "Invalid Image", str(exc))
            return

        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        try:
            tmp.write(data)
            tmp.close()
            set_member_photo(self._center_id, tmp.name, self._db_path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not save photo:\n{exc}")
            return
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

        self._set_photo_pixmap(get_member_photo(self._center_id, self._db_path))
        self._log_event("EDIT", "Photo updated")
```

- [ ] **Step 5: Verify imports**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget, _PhotoLabel, to_jpeg_bytes; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: click the profile photo to add or replace it"
```
End with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 4: Full suite + exe rebuild + manual smoke test

**Files:** none changed

- [ ] **Step 1: Run the full test suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 2: Rebuild the exe**

```
powershell -Command "try { Stop-Process -Name MemberManager -Force -ErrorAction Stop } catch {}"
.venv\Scripts\pyinstaller MemberManager.spec
```
Expected: `Build complete! ... dist`

- [ ] **Step 3: Manual smoke test** (requires the real Access DB in Settings)

Launch `dist\MemberManager.exe`, open a member:
- The header photo shows a pointing-hand cursor and "Click to change photo" tooltip.
- Click it on a member **without** a photo → pick a JPG → it saves and shows
  immediately; reopen the member → the photo persists.
- Click it on a member **with** a photo → a "Replace existing photo?" confirmation
  appears; confirm → pick a new image (try a **PNG**) → it converts and shows;
  declining the confirmation leaves the photo unchanged.
- Cancel the file picker → nothing changes.
- The **Events** tab shows a "Photo updated" entry for each change.

---

## Self-Review Notes

- **Spec coverage:** DAO writable `set_member_photo` (replace existing, drop cached
  read handle) → Task 1. `to_jpeg_bytes` JPEG normalization → Task 2. Clickable
  `_PhotoLabel`, confirm-on-replace, file picker, temp-file write, reload, audit log
  → Task 3. Suite/exe/manual → Task 4.
- **Type consistency:** `set_member_photo(center_id, image_path, db_path)`;
  `to_jpeg_bytes(src_path) -> bytes`; `_PhotoLabel.clicked` signal →
  `_change_photo`; `_set_photo_pixmap(photo_bytes)` sets `self._has_photo`;
  `self._photo_label` is the `_PhotoLabel`. Reload uses the unchanged
  `get_member_photo`.
- **No placeholders:** every step has full code and exact commands/expected output.
  The DAO write and click flow are verified manually (need Access + win32com + a
  writable DB); `to_jpeg_bytes` is unit-tested.
