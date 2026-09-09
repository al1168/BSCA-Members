# BSCA Member Manager

## Product Purpose
Internal desktop tool for non-technical staff at an adult day health care center (BSCA) to manage member records. Staff use this to add new members, maintain their contact info, record authorizations, availability, and absences, and view audit history. The tool writes to a shared Microsoft Access database used by the monthly schedule generator.

## Users
Non-technical administrative staff — typically 1-3 people at a single office location. They are comfortable with basic computer use but not developers. They need clear labels, obvious affordances, and forgiving workflows (e.g. can save a partial member record and complete it later).

## Register
product

## Brand
- Name: BSCA Member Manager
- Tone: calm, professional, trustworthy. Not playful. Not clinical. Functional and approachable.
- Anti-references: loud SaaS dashboards, neon/crypto aesthetics, medical-white sterility, generic admin templates

## Strategic Principles
- Clarity over density: each screen has one primary action
- Non-destructive by default: confirmations before deletes, warnings before leaving unsaved changes
- Incomplete is OK: members can be created without full data; missing fields surface as visible warnings
- Audit everything: every data change is logged with timestamp for accountability

## Key Surfaces
- Member list + detail panel (side-by-side, main window)
- Add New Member wizard (4-step: Contact Info, Enrollment, Auths & Availability, Review)
- Per-member tabs: Info, Enrollments, Authorizations, Availability, Absences, Events
- Global events log (audit trail, 30-day TTL, stored in local SQLite)
- Company Calendar dialog (holidays + weekly operating hours)

## Tech Stack
PyQt6 desktop app on Windows. Styled with Qt stylesheets (QSS). Dark theme — staff work in an indoor office environment with controlled lighting.
