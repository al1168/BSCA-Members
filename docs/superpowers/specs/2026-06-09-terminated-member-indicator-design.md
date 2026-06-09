# Terminated-Member Indicator — Design Spec

**Date:** 2026-06-09
**Status:** Approved (pending spec review)

## Goal

Make terminated members unmistakable: a dimmed name + red "⊘ TERMINATED" tag in
the left member list, and a red "⊘ Terminated" badge in the profile header.

## Definition of "terminated" (from brainstorming)

There is no status field. A member is **terminated** when their **latest**
enrollment (the one with the greatest start date) has an **end date on file**
(whether that date is in the past or the future). Rules:

- No enrollments at all → **not** terminated.
- Latest enrollment has `end_date is None` (ongoing) → **not** terminated.
- Latest enrollment has any `end_date` set → **terminated**.

Picking the *latest* enrollment means re-enrollment works: an old ended
enrollment plus a newer ongoing one is **not** terminated.

## Background (current state)

- `db/members.py`: `get_all_members(db_path)` runs a Contacts-only query
  (`Center ID, Last Name, First Name, Health Plan`) — no enrollment data.
  `terminate_enrollment` sets an enrollment's `end_date` to today.
  Enrollment dicts have `id, center_id, start_date, end_date` (dates; via
  `map_enrollment_row`). `_connect` opens a write connection (used by
  `get_all_members`). `_access_date(value)` (added earlier) converts Access
  Date/Time → `date` (None-safe).
- `gui/main_window.py`: the sidebar is a `QListWidget` (`self._member_list`).
  `_load_members` calls `get_all_members` then `_populate_list`. `_populate_list`
  builds each `QListWidgetItem` with a 2-line label
  `"{last}, {first}\n{center_id} · {health_plan}"` and stores `center_id` in
  `Qt.ItemDataRole.UserRole`. `_filter_members` re-runs `_populate_list` on a
  filtered subset.
- `gui/member_tabs.py`: `_build_ui` header top row holds the name, the plan badge,
  a stretch, then the conditional `⚠` warning badge. `self._enrollments` is loaded
  in `_load_data`. Badges are themed by object name in `gui/theme.py`
  (`warning_badge` is the red one; `plan_badge` is the accent pill).

## Architecture

### 1. Detection (`db/members.py`)

```python
def is_terminated(enrollments: list[dict]) -> bool:
    """True when the member's latest enrollment (by start date) has an end date.
    No enrollments -> False; a latest ongoing enrollment -> False."""
    if not enrollments:
        return False
    latest = max(enrollments, key=lambda e: e.get("start_date") or date.min)
    return latest.get("end_date") is not None


def terminated_ids_from_rows(rows) -> set[int]:
    """Group raw (center_id, start_date, end_date) rows by member and return the
    set of terminated center ids. Pure — no DB — so it is unit-testable."""
    from collections import defaultdict
    by_member: dict[int, list[dict]] = defaultdict(list)
    for cid, start, end in rows:
        if cid is None:
            continue
        by_member[int(cid)].append(
            {"start_date": _access_date(start), "end_date": _access_date(end)}
        )
    return {cid for cid, enrs in by_member.items() if is_terminated(enrs)}


def get_terminated_center_ids(db_path: str) -> set[int]:
    """Center ids of terminated members, computed from all Enrollment rows in
    one query (mirrors get_all_members' connection handling)."""
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT [Center ID], [start_date], [end_date] FROM [Enrollment]")
        return terminated_ids_from_rows(cur.fetchall())
    finally:
        conn.close()
```

(`date` and `_access_date` already exist in `db/members.py`.)

### 2. Member list (`gui/main_window.py`)

- A module-level role constant: `TERMINATED_ROLE = Qt.ItemDataRole.UserRole + 1`.
- `_load_members`: after `get_all_members`, also load
  `self._terminated_ids = get_terminated_center_ids(db_path)` (guarded by the same
  try/except; default to an empty set on error so the list still renders).
  Initialize `self._terminated_ids = set()` where the other state is set up.
- `_populate_list`: keep the existing label/`UserRole`, and additionally set
  `item.setData(TERMINATED_ROLE, m["center_id"] in self._terminated_ids)`.
- Install a delegate on the list: `self._member_list.setItemDelegate(
  _MemberItemDelegate(self._member_list))`.
- `_MemberItemDelegate(QStyledItemDelegate)`:
  - For a **non-terminated** item (`TERMINATED_ROLE` falsy): call `super().paint(...)`
    (default rendering — no behavior change).
  - For a **terminated** item: paint the selection/hover background using the style
    (`QApplication.style().drawPrimitive`/`drawControl` with the option), then render
    the item text via a `QTextDocument` as HTML:
    `"{last}, {first}<br><span style='color:{muted}'>{cid} · {plan}</span>
    &nbsp;&nbsp;<span style='color:{red}'>⊘ TERMINATED</span>"` — name in the muted
    token color, the tag in the error/red token color. The HTML is built from the
    item's display text (split on `\n`) so no extra data plumbing is needed.
  - `sizeHint`: return the base size hint (rows already fit two lines at the existing
    34px-ish item height; bump only if the HTML needs it).
  - **Colors:** the delegate takes two hex strings at construction —
    `_MemberItemDelegate(parent, muted_hex, tag_hex)`. `MainWindow` supplies them
    from the active theme's tokens: `muted_hex = tokens['text2']`,
    `tag_hex = tokens['error']`, where `tokens = DARK if theme == "dark" else LIGHT`
    (imported from `gui.theme`). On theme toggle (where `apply_theme` is already
    called), `MainWindow` updates the delegate's two colors and calls
    `self._member_list.viewport().update()` so terminated rows restyle immediately.

### 3. Profile header (`gui/member_tabs.py`)

- New QSS `QLabel#terminated_badge` in `gui/theme.py` `build_qss` (both themes):
  solid `error` background, near-white `#f4f6fd` text, rounded, bold — visually
  louder than the outline `warning_badge`.
- In `_build_ui`, after the plan-badge block and before `top_row.addStretch()`:

```python
        from db.members import is_terminated
        if is_terminated(self._enrollments):
            term_badge = QLabel("⊘ Terminated")
            term_badge.setObjectName("terminated_badge")
            term_badge.setMaximumHeight(26)
            top_row.addWidget(term_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
```

## Data flow

- List: `get_terminated_center_ids` (one query) → `self._terminated_ids` →
  per-item `TERMINATED_ROLE` flag → delegate paints dimmed name + red tag.
- Profile: `self._enrollments` (already loaded) → `is_terminated` → header badge.

## Error handling / edge cases

- No enrollments → not terminated (no tag, no badge).
- `get_terminated_center_ids` failure → empty set (list renders without tags;
  no crash).
- Search filter re-renders the list; the flag is keyed by `center_id`, so terminated
  styling persists across filtering.
- A terminated member may also have an expired-auth warning; both can show — the
  terminated badge is the dominant indicator.

## Testing

- `is_terminated`: empty → False; latest ongoing (`end_date None`) → False; latest
  with a past end → True; latest with a future end → True; re-enrollment (old ended
  with earlier start + newer ongoing) → False.
- `terminated_ids_from_rows`: rows for several members (mix of ongoing, ended,
  re-enrolled, no-enrollment) → exactly the expected terminated set; rows with a
  `None` center id are skipped.
- Theme test: `build_qss(DARK)` and `build_qss(LIGHT)` each contain
  `QLabel#terminated_badge`.
- Manual: the list shows dimmed name + red "⊘ TERMINATED" for terminated members and
  normal rows for active ones; the profile shows the red "⊘ Terminated" badge;
  search still works; both light and dark read correctly.

## Out of scope

- Filtering or hiding terminated members from the list.
- A "reactivate" action.
- Changing how termination is stored (it stays the enrollment end date).
