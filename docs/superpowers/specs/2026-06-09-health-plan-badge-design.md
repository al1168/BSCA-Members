# Health Plan Badge — Design Spec

**Date:** 2026-06-09
**Status:** Approved (pending spec review)

## Goal

Make a member's health plan immediately visible by showing it as a colored pill
badge in the member-profile header, beside the name. The badge is display-only and
appears on every tab.

## Background (current state)

In `gui/member_tabs.py`:

- The header top row (`_build_ui`, ~lines 276-291) shows the name + ID on the left,
  a stretch, then a conditional `⚠` warning badge (`QLabel` object name
  `warning_badge`) on the right. Below it is the always-visible Notes band.
- The health plan currently appears in two low-key places: the Medical-section
  read-only field `self._info_plan`, and appended to the Schedule "Auth Period"
  line (`… · HF`, ~lines 381-384). It is display-only — synced from the latest
  authorization via `sync_health_plan_from_latest_auth`.
- `self._member.get("health_plan", "")` holds the value (one of `HEALTH_PLANS` in
  `db/members.py`, e.g. `HF`); it may be empty.
- Badges are themed by object name in `gui/theme.py` `build_qss(t)` (e.g.
  `warning_badge`). Accent tokens available: `accent`, `accent_bg`, `accent_text`.

## Decision (from brainstorming)

- Placement: header top row, **immediately after the name/ID**, before the stretch
  (so the warning badge stays on the right).
- Treatment: an **accent** pill (distinct from the red warning badge), using the
  existing accent token family already used by the Settings button and the "on"
  weekday chips.
- **Additive only:** keep the Medical-section Health Plan field AND the Auth Period
  `· HF` suffix exactly as they are. The badge is added on top for prominence.
- Conditional: show the badge only when the member has a non-empty health plan.

## Architecture

### Theme (`gui/theme.py`)

Add one rule inside `build_qss(t)` (so both DARK and LIGHT inherit it from their
token dicts), placed near `warning_badge`:

```python
QLabel#plan_badge {{
    background-color: {t['accent_bg']};
    color: {t['accent_text']};
    border: 1px solid {t['accent']};
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}}
```

(Baseline values, consistent with the existing badge/pill styling; exact numbers
may be nudged during implementation but the tokens and structure are fixed.)

### Header (`gui/member_tabs.py` `_build_ui`)

In the top row, between `top_row.addWidget(name_label)` and `top_row.addStretch()`,
add a conditional plan badge:

```python
        top_row.addWidget(name_label)
        plan = self._member.get("health_plan", "")
        if plan:
            plan_badge = QLabel(plan)
            plan_badge.setObjectName("plan_badge")
            plan_badge.setToolTip("Health Plan")
            plan_badge.setMaximumHeight(26)
            top_row.addWidget(plan_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        top_row.addStretch()
```

The existing warning-badge block (after the stretch) and everything else is
unchanged. The Medical field and the Auth Period suffix are untouched.

## Components / data flow

- `self._member["health_plan"]` (already loaded by `get_member_context`) → the
  badge text. No new data, no DB, no writes. Tooltip clarifies the bare code.

## Error handling / edge cases

- Empty/missing health plan → no badge (header shows just name/ID, as today).
- Long codes (all `HEALTH_PLANS` values are short, ≤6 chars) fit the pill; the
  badge sizes to its content.

## Testing

- Theme test: `build_qss(DARK)` and `build_qss(LIGHT)` each contain
  `QLabel#plan_badge` (mirrors the existing chip-style test).
- The header wiring (badge shown when a plan exists, hidden when blank) is verified
  manually, since constructing `MemberTabsWidget` requires a full member context.
- Then: full suite, exe rebuild, and a manual check — a member with a plan shows
  the accent badge beside the name on every tab and on hover shows "Health Plan";
  a member with no plan shows no badge; the Medical field and the Auth Period line
  are unchanged.

## Out of scope

- Making the health plan editable (stays synced from authorizations).
- Removing or changing the Medical field or the Auth Period `· HF` suffix.
- Any other header/badge changes.
