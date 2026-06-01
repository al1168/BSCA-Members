# Profile Page Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add member photo display, expand the Info tab to show all Contacts columns with a Schedule Summary, and increase the Add New Member wizard minimum size.

**Architecture:** Three independent changes touching `db/members.py` (data layer), `gui/member_tabs.py` (Info tab UI), and `gui/wizard/wizard.py` (size). Photo is fetched via DAO (pywin32) in a separate function since pyodbc cannot read Access Attachment fields. The expanded Info tab uses `get_member_context()` extended to fetch all Contacts columns in the existing single connection.

**Tech Stack:** Python 3.11, PyQt6, pyodbc (Access reads/writes), pywin32/DAO (photo only), pytest

---

## File Map

```
db/members.py          modify — add get_member_photo(), extend get_member_context() + UPDATE_CONTACT + update_contact()
gui/member_tabs.py     modify — photo in header, grouped scrollable Info tab, extended save/discard/dirty
gui/wizard/wizard.py   modify — setMinimumSize(700, 640)
requirements.txt       modify — add pywin32
tests/test_db_members.py             modify — add tests for new UPDATE_CONTACT columns
tests/test_db_members_integration.py modify — add test for get_member_photo
```

---

## Task 1: pywin32 dependency + get_member_photo()

**Files:**
- Modify: `requirements.txt`
- Modify: `db/members.py`
- Modify: `tests/test_db_members_integration.py`

- [ ] **Step 1: Add pywin32 to requirements.txt**

Edit `requirements.txt` to add `pywin32>=306` after `pyodbc>=5.0`:

```
PyQt6>=6.6.0
pyodbc>=5.0
pywin32>=306
pyinstaller>=6.0.0
pytest>=8.0
pytest-qt>=4.4
# install bsca-core locally:
# pip install -e "C:\Users\luald\OneDrive\Desktop\BSCA"
```

- [ ] **Step 2: Verify pywin32 is already installed**

```
.venv\Scripts\python -c "import win32com.client; print('OK')"
```

Expected: `OK` (pywin32 was installed earlier in the session)

- [ ] **Step 3: Write failing integration test for get_member_photo**

Add to `tests/test_db_members_integration.py` (at the bottom):

```python
def test_get_member_photo_returns_bytes_or_none():
    from db.members import get_all_members, get_member_photo
    members = get_all_members(TEST_DB)
    # Test with first member — may or may not have a photo
    first = members[0]
    result = get_member_photo(first["center_id"], TEST_DB)
    assert result is None or isinstance(result, bytes)


def test_get_member_photo_bytes_start_with_jpeg_header():
    """If a photo exists it must be a valid JPEG (starts with FF D8)."""
    from db.members import get_all_members, get_member_photo
    members = get_all_members(TEST_DB)
    for m in members[:20]:  # check first 20 to find one with a photo
        data = get_member_photo(m["center_id"], TEST_DB)
        if data is not None:
            assert data[:2] == b'\xff\xd8', f"Not a JPEG for center_id={m['center_id']}"
            return
    # If no photos found in first 20, skip (not a failure)


def test_get_member_photo_missing_id_returns_none():
    from db.members import get_member_photo
    result = get_member_photo(999999999, TEST_DB)
    assert result is None
```

- [ ] **Step 4: Run to verify failure**

```
.venv\Scripts\pytest tests/test_db_members_integration.py::test_get_member_photo_returns_bytes_or_none -v
```

Expected: `ImportError: cannot import name 'get_member_photo'`

- [ ] **Step 5: Implement get_member_photo() in db/members.py**

Add after the `get_all_members` function:

```python
def get_member_photo(center_id: int, db_path: str) -> bytes | None:
    """Return raw JPEG bytes from the Access Attachment field, or None.

    Access Attachment fields are not readable via pyodbc; this function
    uses DAO (win32com) instead. Failures are silently swallowed because
    the photo is non-critical — the UI falls back to a placeholder.
    """
    if not os.path.exists(db_path):
        return None
    try:
        import win32com.client
        dao = win32com.client.Dispatch("DAO.DBEngine.120")
        db = dao.OpenDatabase(db_path)
        try:
            rs = db.OpenRecordset(
                f"SELECT * FROM [Contacts] WHERE [Center ID]={center_id}"
            )
            if rs.EOF:
                rs.Close()
                return None
            photo_field = rs.Fields("Photo")
            attach_rs = photo_field.Value
            if attach_rs.EOF:
                attach_rs.Close()
                rs.Close()
                return None
            raw = attach_rs.Fields("FileData").Value
            data = bytes(raw) if raw is not None else None
            attach_rs.Close()
            rs.Close()
            return data
        finally:
            db.Close()
    except Exception:
        return None
```

- [ ] **Step 6: Run tests**

```
.venv\Scripts\pytest tests/test_db_members_integration.py -k "photo" -v
```

Expected: `3 passed` (or 2 passed + 1 skipped if no photos found in first 20 members)

- [ ] **Step 7: Commit**

```bash
git add requirements.txt db/members.py tests/test_db_members_integration.py
git commit -m "feat: add get_member_photo() via DAO for Access Attachment field"
```

---

## Task 2: Extend get_member_context() and update_contact()

**Files:**
- Modify: `db/members.py`
- Modify: `tests/test_db_members.py`
- Modify: `tests/test_db_members_integration.py`

- [ ] **Step 1: Write failing unit tests for new UPDATE_CONTACT**

Add to `tests/test_db_members.py`:

```python
def test_update_contact_targets_all_editable_fields():
    from db.members import UPDATE_CONTACT
    for col in (
        "[Last Name]", "[First Name]", "[Chinese Name]", "[Gender]", "[DOB]",
        "[Member ID]", "[Health Plan]", "[Medicaid]", "[Medicare]", "[SSN]",
        "[Language]", "[Case Manager]", "[Home Tell]", "[Cell]", "[Address]",
        "[Emergency]", "[PCP]", "[Hospital]", "[HHA]", "[Admission Date]", "[Notes]",
    ):
        assert col in UPDATE_CONTACT, f"Missing column in UPDATE_CONTACT: {col}"
    assert "WHERE [Center ID]=?" in UPDATE_CONTACT
```

- [ ] **Step 2: Run to verify failure**

```
.venv\Scripts\pytest tests/test_db_members.py::test_update_contact_targets_all_editable_fields -v
```

Expected: `FAIL — AssertionError: Missing column in UPDATE_CONTACT: [Chinese Name]`

- [ ] **Step 3: Write failing integration test for expanded member dict**

Add to `tests/test_db_members_integration.py`:

```python
def test_get_member_context_returns_all_contact_fields():
    from db.members import get_all_members, get_member_context
    members = get_all_members(TEST_DB)
    ctx = get_member_context(members[0]["center_id"], TEST_DB)
    m = ctx["member"]
    for key in (
        "center_id", "last_name", "first_name", "chinese_name",
        "gender", "dob", "member_id", "health_plan",
        "medicaid", "medicare", "ssn", "language",
        "case_manager", "home_tell", "cell", "address",
        "emergency", "pcp", "hospital", "hha",
        "admission_date", "notes",
    ):
        assert key in m, f"Missing key in member context: {key}"
        assert m[key] is not None, f"Key {key!r} is None (should be '' for missing)"
```

- [ ] **Step 4: Run to verify failure**

```
.venv\Scripts\pytest tests/test_db_members_integration.py::test_get_member_context_returns_all_contact_fields -v
```

Expected: `FAIL — AssertionError: Missing key in member context: chinese_name`

- [ ] **Step 5: Update db/members.py — new UPDATE_CONTACT constant and extended update_contact()**

Replace the `UPDATE_CONTACT` constant and `update_contact()` function:

```python
UPDATE_CONTACT = (
    "UPDATE [Contacts] SET "
    "[Last Name]=?, [First Name]=?, [Chinese Name]=?, [Gender]=?, [DOB]=?, "
    "[Member ID]=?, [Health Plan]=?, [Medicaid]=?, [Medicare]=?, [SSN]=?, "
    "[Language]=?, [Case Manager]=?, [Home Tell]=?, [Cell]=?, [Address]=?, "
    "[Emergency]=?, [PCP]=?, [Hospital]=?, [HHA]=?, [Admission Date]=?, [Notes]=? "
    "WHERE [Center ID]=?"
)
```

Replace `update_contact()`:

```python
def update_contact(
    center_id: int,
    last_name: str,
    first_name: str,
    chinese_name: str,
    gender: str,
    dob: str,
    member_id: str,
    health_plan: str,
    medicaid: str,
    medicare: str,
    ssn: str,
    language: str,
    case_manager: str,
    home_tell: str,
    cell: str,
    address: str,
    emergency: str,
    pcp: str,
    hospital: str,
    hha: str,
    admission_date: str,
    notes: str,
    db_path: str,
) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            UPDATE_CONTACT,
            (
                last_name, first_name, chinese_name, gender, dob,
                member_id, health_plan, medicaid, medicare, ssn,
                language, case_manager, home_tell, cell, address,
                emergency, pcp, hospital, hha, admission_date, notes,
                center_id,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

- [ ] **Step 6: Update get_member_context() in db/members.py**

Replace the member SELECT inside `get_member_context()`:

```python
        c.execute(
            "SELECT [Center ID],[Last Name],[First Name],[Chinese Name],[DOB],"
            "[Health Plan],[Member ID],[Medicaid],[Medicare],[SSN],[Language],"
            "[Case Manager],[Home Tell],[Cell],[Address],[Emergency],[PCP],"
            "[Hospital],[HHA],[Notes],[Gender],[Admission Date] "
            "FROM [Contacts] WHERE [Center ID]=?",
            center_id,
        )
        row = c.fetchone()
        if row:
            member = {
                "center_id":      int(row[0]) if row[0] is not None else center_id,
                "last_name":      row[1]  or "",
                "first_name":     row[2]  or "",
                "chinese_name":   row[3]  or "",
                "dob":            str(row[4]) if row[4] else "",
                "health_plan":    row[5]  or "",
                "member_id":      row[6]  or "",
                "medicaid":       row[7]  or "",
                "medicare":       row[8]  or "",
                "ssn":            row[9]  or "",
                "language":       row[10] or "",
                "case_manager":   row[11] or "",
                "home_tell":      row[12] or "",
                "cell":           row[13] or "",
                "address":        row[14] or "",
                "emergency":      row[15] or "",
                "pcp":            row[16] or "",
                "hospital":       row[17] or "",
                "hha":            row[18] or "",
                "notes":          row[19] or "",
                "gender":         row[20] or "",
                "admission_date": str(row[21]) if row[21] else "",
            }
        else:
            member = {}
```

- [ ] **Step 7: Run all tests**

```
.venv\Scripts\pytest tests/test_db_members.py tests/test_db_members_integration.py -v
```

Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add db/members.py tests/test_db_members.py tests/test_db_members_integration.py
git commit -m "feat: expand get_member_context() and update_contact() to full Contacts schema"
```

---

## Task 3: Photo in member header + expanded grouped Info tab

**Files:**
- Modify: `gui/member_tabs.py`

This task rewrites `_build_ui()` (header section), `_make_info_tab()`, `_discard_info()`, `_save_info()`, and `_setup_dirty_tracking()`. It also adds a `_make_photo_label()` helper and two pure-Python helpers for the Schedule Summary.

- [ ] **Step 1: Add _make_photo_label() helper to MemberTabsWidget**

Add this method to `MemberTabsWidget` (after `_load_data`):

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
        # Crop to a centered 80×80 square
        if pix.width() > 80 or pix.height() > 80:
            x = (pix.width() - 80) // 2
            y = (pix.height() - 80) // 2
            pix = pix.copy(x, y, 80, 80)
        lbl.setPixmap(pix)
    else:
        # Draw a gray circle with a white person silhouette placeholder
        pix = QPixmap(80, 80)
        pix.fill(QtCore.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor("#3a3a3a")))
        painter.setPen(QtCore.NoPen)
        painter.drawEllipse(0, 0, 80, 80)
        painter.setBrush(QBrush(QColor("#888888")))
        painter.drawEllipse(28, 12, 24, 24)   # head
        painter.drawEllipse(12, 46, 56, 40)   # body
        painter.end()
        lbl.setPixmap(pix)

    return lbl
```

- [ ] **Step 2: Add _active_authorization() and _enrollment_start() helpers**

Add these two static helpers to `MemberTabsWidget`:

```python
@staticmethod
def _active_authorization(authorizations: list[dict]) -> dict | None:
    """Return the auth row covering today, preferring latest start. None if none."""
    from datetime import date
    today = date.today()
    candidates = [
        a for a in authorizations
        if a.get("effective_start") and a.get("effective_end")
        and a["effective_start"] <= today <= a["effective_end"]
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda a: a["effective_start"])

@staticmethod
def _enrollment_start(enrollments: list[dict]):
    """Return the earliest enrollment start_date, or None."""
    dates = [e["start_date"] for e in enrollments if e.get("start_date")]
    return min(dates) if dates else None
```

- [ ] **Step 3: Update _build_ui() header to include photo**

Replace the header section inside `_build_ui()` (lines that build `header = QHBoxLayout()` through `layout.addLayout(header)`):

```python
        # Header row
        header = QHBoxLayout()
        header.setSpacing(14)

        # Photo
        header.addWidget(self._make_photo_label())

        # Name + ID
        name_col = QVBoxLayout()
        name = f"{self._member.get('last_name', '')}, {self._member.get('first_name', '')}"
        cid = str(self._center_id)
        name_label = QLabel(f"<b style='font-size:15px'>{name}</b>"
                            f"<span style='color:gray;font-size:12px'> &nbsp;ID {cid}</span>")
        name_label.setTextFormat(Qt.TextFormat.RichText)
        name_col.addWidget(name_label)
        name_col.addStretch()
        header.addLayout(name_col)
        header.addStretch()

        missing = self._missing()
        if missing:
            badge = QLabel("⚠ Missing: " + ", ".join(missing))
            badge.setObjectName("warning_badge")
            header.addWidget(badge)

        layout.addLayout(header)
```

- [ ] **Step 4: Rewrite _make_info_tab()**

Replace the entire `_make_info_tab()` method:

```python
    def _make_info_tab(self) -> QWidget:
        from PyQt6.QtWidgets import (
            QFormLayout, QLineEdit, QComboBox, QTextEdit,
            QGroupBox, QScrollArea,
        )
        from db.members import HEALTH_PLANS

        m = self._member

        # ── widget factory helpers ────────────────────────────────────────
        def field(key: str) -> QLineEdit:
            w = QLineEdit(m.get(key, "") or "")
            return w

        # ── Identity ─────────────────────────────────────────────────────
        grp_identity = QGroupBox("Identity")
        f_identity = QFormLayout(grp_identity)
        f_identity.setSpacing(8)

        self._info_first = field("first_name")
        self._info_last  = field("last_name")
        self._info_chinese = field("chinese_name")
        self._info_gender  = field("gender")
        self._info_dob     = field("dob")
        self._info_cid     = QLineEdit(str(self._center_id))
        self._info_cid.setReadOnly(True)
        self._info_member_id = field("member_id")

        for lbl, w in [
            ("First Name", self._info_first),
            ("Last Name",  self._info_last),
            ("Chinese Name", self._info_chinese),
            ("Gender",     self._info_gender),
            ("DOB",        self._info_dob),
            ("Center ID",  self._info_cid),
            ("Member ID",  self._info_member_id),
        ]:
            f_identity.addRow(lbl, w)

        # ── Contact ──────────────────────────────────────────────────────
        grp_contact = QGroupBox("Contact")
        f_contact = QFormLayout(grp_contact)
        f_contact.setSpacing(8)

        self._info_address   = field("address")
        self._info_home_tell = field("home_tell")
        self._info_cell      = field("cell")
        self._info_emergency = field("emergency")

        for lbl, w in [
            ("Address",   self._info_address),
            ("Home Phone", self._info_home_tell),
            ("Cell",      self._info_cell),
            ("Emergency", self._info_emergency),
        ]:
            f_contact.addRow(lbl, w)

        # ── Medical ──────────────────────────────────────────────────────
        grp_medical = QGroupBox("Medical")
        f_medical = QFormLayout(grp_medical)
        f_medical.setSpacing(8)

        self._info_plan     = QComboBox()
        self._info_plan.addItems(HEALTH_PLANS)
        idx = self._info_plan.findText(m.get("health_plan", ""))
        self._info_plan.setCurrentIndex(idx if idx >= 0 else 0)

        self._info_medicaid  = field("medicaid")
        self._info_medicare  = field("medicare")
        self._info_ssn       = field("ssn")
        self._info_pcp       = field("pcp")
        self._info_hospital  = field("hospital")
        self._info_hha       = field("hha")
        self._info_language  = field("language")

        for lbl, w in [
            ("Health Plan", self._info_plan),
            ("Medicaid",   self._info_medicaid),
            ("Medicare",   self._info_medicare),
            ("SSN",        self._info_ssn),
            ("PCP",        self._info_pcp),
            ("Hospital",   self._info_hospital),
            ("HHA",        self._info_hha),
            ("Language",   self._info_language),
        ]:
            f_medical.addRow(lbl, w)

        # ── Care ─────────────────────────────────────────────────────────
        grp_care = QGroupBox("Care")
        f_care = QFormLayout(grp_care)
        f_care.setSpacing(8)

        self._info_case_manager   = field("case_manager")
        self._info_admission_date = field("admission_date")
        self._info_notes = QTextEdit(m.get("notes", "") or "")
        self._info_notes.setFixedHeight(72)

        f_care.addRow("Case Manager",   self._info_case_manager)
        f_care.addRow("Admission Date", self._info_admission_date)
        f_care.addRow("Notes",          self._info_notes)

        # ── Schedule Summary (read-only) ──────────────────────────────────
        grp_sched = QGroupBox("Schedule Summary")
        f_sched = QFormLayout(grp_sched)
        f_sched.setSpacing(8)

        enroll_start = self._enrollment_start(self._enrollments)
        enroll_lbl = QLineEdit(str(enroll_start) if enroll_start else "—")
        enroll_lbl.setReadOnly(True)

        active_auth = self._active_authorization(self._authorizations)
        if active_auth:
            day_map = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}
            days_str = " ".join(
                day_map[d] for d in sorted(
                    self.decode_auth_days_static(active_auth.get("auth_days", ""))
                )
            )
            auth_text = (f"{active_auth['effective_start']} – "
                         f"{active_auth['effective_end']}  [{days_str}]")
        else:
            auth_text = "None"
        auth_lbl = QLineEdit(auth_text)
        auth_lbl.setReadOnly(True)

        f_sched.addRow("Enrollment Start", enroll_lbl)
        f_sched.addRow("Active Auth",      auth_lbl)

        # ── Assemble in scroll area ───────────────────────────────────────
        scroll_content = QWidget()
        vbox = QVBoxLayout(scroll_content)
        vbox.setSpacing(10)
        vbox.setContentsMargins(0, 8, 8, 8)
        for grp in (grp_identity, grp_contact, grp_medical, grp_care, grp_sched):
            vbox.addWidget(grp)
        vbox.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(scroll_content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 8, 0, 0)
        outer_layout.setSpacing(8)
        outer_layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_discard = QPushButton("Discard")
        btn_discard.clicked.connect(self._discard_info)
        btn_save = QPushButton("Save Changes")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save_info)
        btn_row.addWidget(btn_discard)
        btn_row.addWidget(btn_save)
        outer_layout.addLayout(btn_row)

        return outer

    @staticmethod
    def decode_auth_days_static(value: str) -> set[int]:
        if not value:
            return set()
        return {int(x) for x in value.split(",") if x.strip()}
```

- [ ] **Step 5: Rewrite _discard_info()**

Replace the existing `_discard_info()` method:

```python
    def _discard_info(self):
        m = self._member
        self._info_first.setText(m.get("first_name", "") or "")
        self._info_last.setText(m.get("last_name", "") or "")
        self._info_chinese.setText(m.get("chinese_name", "") or "")
        self._info_gender.setText(m.get("gender", "") or "")
        self._info_dob.setText(m.get("dob", "") or "")
        self._info_member_id.setText(m.get("member_id", "") or "")
        idx = self._info_plan.findText(m.get("health_plan", ""))
        self._info_plan.setCurrentIndex(idx if idx >= 0 else 0)
        self._info_medicaid.setText(m.get("medicaid", "") or "")
        self._info_medicare.setText(m.get("medicare", "") or "")
        self._info_ssn.setText(m.get("ssn", "") or "")
        self._info_pcp.setText(m.get("pcp", "") or "")
        self._info_hospital.setText(m.get("hospital", "") or "")
        self._info_hha.setText(m.get("hha", "") or "")
        self._info_language.setText(m.get("language", "") or "")
        self._info_address.setText(m.get("address", "") or "")
        self._info_home_tell.setText(m.get("home_tell", "") or "")
        self._info_cell.setText(m.get("cell", "") or "")
        self._info_emergency.setText(m.get("emergency", "") or "")
        self._info_case_manager.setText(m.get("case_manager", "") or "")
        self._info_admission_date.setText(m.get("admission_date", "") or "")
        self._info_notes.setPlainText(m.get("notes", "") or "")
        self._dirty = False
```

- [ ] **Step 6: Rewrite _save_info()**

Replace the existing `_save_info()` method:

```python
    def _save_info(self):
        from db.members import update_contact
        from db.events import open_db, insert_event

        old = self._member
        fields = {
            "last_name":      self._info_last.text().strip(),
            "first_name":     self._info_first.text().strip(),
            "chinese_name":   self._info_chinese.text().strip(),
            "gender":         self._info_gender.text().strip(),
            "dob":            self._info_dob.text().strip(),
            "member_id":      self._info_member_id.text().strip(),
            "health_plan":    self._info_plan.currentText(),
            "medicaid":       self._info_medicaid.text().strip(),
            "medicare":       self._info_medicare.text().strip(),
            "ssn":            self._info_ssn.text().strip(),
            "language":       self._info_language.text().strip(),
            "case_manager":   self._info_case_manager.text().strip(),
            "home_tell":      self._info_home_tell.text().strip(),
            "cell":           self._info_cell.text().strip(),
            "address":        self._info_address.text().strip(),
            "emergency":      self._info_emergency.text().strip(),
            "pcp":            self._info_pcp.text().strip(),
            "hospital":       self._info_hospital.text().strip(),
            "hha":            self._info_hha.text().strip(),
            "admission_date": self._info_admission_date.text().strip(),
            "notes":          self._info_notes.toPlainText().strip(),
        }

        changes = [
            f"{k}: {old.get(k)!r} → {v!r}"
            for k, v in fields.items()
            if v != (old.get(k) or "")
        ]

        if not changes:
            self._dirty = False
            return

        try:
            update_contact(
                center_id=self._center_id,
                last_name=fields["last_name"],
                first_name=fields["first_name"],
                chinese_name=fields["chinese_name"],
                gender=fields["gender"],
                dob=fields["dob"],
                member_id=fields["member_id"],
                health_plan=fields["health_plan"],
                medicaid=fields["medicaid"],
                medicare=fields["medicare"],
                ssn=fields["ssn"],
                language=fields["language"],
                case_manager=fields["case_manager"],
                home_tell=fields["home_tell"],
                cell=fields["cell"],
                address=fields["address"],
                emergency=fields["emergency"],
                pcp=fields["pcp"],
                hospital=fields["hospital"],
                hha=fields["hha"],
                admission_date=fields["admission_date"],
                notes=fields["notes"],
                db_path=self._db_path,
            )
            self._member.update(fields)
            self._dirty = False
            if self._events_path:
                conn = open_db(self._events_path)
                try:
                    insert_event(
                        conn, "EDIT", self._center_id,
                        f"{fields['last_name']}, {fields['first_name']}",
                        "; ".join(changes[:5]),  # cap description length
                    )
                finally:
                    conn.close()
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))
```

- [ ] **Step 7: Extend _setup_dirty_tracking()**

Replace the existing `_setup_dirty_tracking()` method:

```python
    def _setup_dirty_tracking(self):
        self._dirty = False
        line_edits = (
            self._info_first, self._info_last, self._info_chinese,
            self._info_gender, self._info_dob, self._info_member_id,
            self._info_medicaid, self._info_medicare, self._info_ssn,
            self._info_language, self._info_case_manager,
            self._info_home_tell, self._info_cell, self._info_address,
            self._info_emergency, self._info_pcp, self._info_hospital,
            self._info_hha, self._info_admission_date,
        )
        for w in line_edits:
            w.textChanged.connect(lambda: setattr(self, '_dirty', True))
        self._info_plan.currentIndexChanged.connect(lambda: setattr(self, '_dirty', True))
        self._info_notes.textChanged.connect(lambda: setattr(self, '_dirty', True))
```

- [ ] **Step 8: Verify imports work**

```
.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"
```

Expected: `OK`

- [ ] **Step 9: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: photo in member header + expanded grouped Info tab with Schedule Summary"
```

---

## Task 4: Wizard minimum size bump

**Files:**
- Modify: `gui/wizard/wizard.py`

- [ ] **Step 1: Update setMinimumSize in wizard.py**

In `gui/wizard/wizard.py`, change line 20:

```python
        self.setMinimumSize(560, 520)
```

to:

```python
        self.setMinimumSize(700, 640)
```

- [ ] **Step 2: Verify import**

```
.venv\Scripts\python -c "from gui.wizard.wizard import AddMemberWizard; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add gui/wizard/wizard.py
git commit -m "fix: increase Add New Member wizard minimum size to 700x640"
```

---

## Task 5: Full test suite + exe rebuild

**Files:** none changed

- [ ] **Step 1: Run full test suite**

```
.venv\Scripts\pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Rebuild exe**

```
.venv\Scripts\pyinstaller MemberManager.spec
```

Expected: `Build complete! The results are available in: ...\dist`

- [ ] **Step 3: Smoke test the exe**

Launch `dist\MemberManager.exe`, configure the DB path in Settings, click a member, verify:
- Photo appears in header (or gray placeholder if no photo)
- Info tab has 5 grouped sections (Identity, Contact, Medical, Care, Schedule Summary)
- Schedule Summary shows Enrollment Start and Active Auth
- Wizard opens at a larger size
