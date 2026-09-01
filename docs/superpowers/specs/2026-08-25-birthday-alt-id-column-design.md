# Birthday Report: Alt ID Column

**Date:** 2026-08-25
**Status:** Approved

## Goal

Add an "Alt ID" column to the monthly birthdays report, immediately after
Center Id, showing each member's alt id as the app displays it.

## Background

`[Contacts].[alt_id]` is stored encrypted (format-preserving Feistel cipher,
`db/alt_id_crypto.py`). At corpus load, `decrypt_corpus_alt_ids`
(`gui/main_window.py`) replaces each in-memory member's `alt_id` with its
decrypted display value when the session password from Settings is set.
`BirthdayReportDialog` receives that pre-decrypted member list, so the export
needs no crypto code — it carries the corpus value through.

## Behavior

The Alt ID cell matches the app's display everywhere else:

- Password set in Settings → decrypted alt id.
- No password → the raw stored number (same as the profile shows).
- Member has no alt id → blank cell.

## Changes (all in `db/export.py` + tests)

- `BIRTHDAY_COLUMNS` → `["Center Id", "Alt ID", "Name", "Birthday", "Sign",
  "Date"]` ("Alt ID" matches the profile label).
- `members_with_birthday_in_month` adds `"alt_id": m.get("alt_id")` to each
  row dict.
- `write_birthday_xlsx` writes the alt id cell after Center Id (blank when
  `None`), centered like Center Id (`center_cols={1, 2, 4}`), with widths
  rebalanced — Sign shrinks 34 → 24 — so the sheet still fits the printable
  page at the fixed 100% print scale.
- No GUI changes.

## Testing

Extend `tests/test_birthday_report.py`:

- Row dicts carry `alt_id` (value and `None` cases).
- Written sheet: "Alt ID" header in column B, value in B for a member with an
  alt id, blank for one without.
