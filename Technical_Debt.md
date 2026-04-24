# Technical Debt

Known technical debt catalogued for future resolution. Priority: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When an item in this file is resolved, **delete its entry from this file** and add a corresponding entry to [`Technical_Debt_Paid_Off.md`](Technical_Debt_Paid_Off.md) documenting what was changed and how. This file should only ever contain debt that has not yet been addressed.

> **Audit date:** 2026-04-20 · Files scanned: entire project (`backend/`, `frontend/`, config files)

---

## TD-009 · Transit photo manifest incomplete — missing photos for 5 hardcoded entries
- **File**: [frontend/src/App.jsx](frontend/src/App.jsx#L18)
- **Line(s)**: 18, 25–29
- **Category**: Missing implementation / TODO-FIXME
- **Priority**: Medium
- **Description**: The `PHOTOS` array contains 5 entries with hardcoded photo paths but no images have been sourced and added to `public/transit-photos/`. A comment explicitly marks this as `HUMAN_TODO`. When any photo fails to load (via `onError`), the placeholder silently hides but users see an empty space instead of a fallback. This is a minor UX issue but blocks the transit photo feature from being production-ready.
- **Suggested Improvement**: Either (1) source the actual photos and commit them to the repo, or (2) remove the PHOTOS array entirely and disable the transit-photo component if photos won't be used. If keeping the feature, add a fallback image or cached web-accessible URL for each photo.

---

## TD-010 · Bus fullness filter is disabled and commented out — waiting on CTA API data
- **File**: [frontend/src/App.jsx](frontend/src/App.jsx#L455-L467)
- **Line(s)**: 455–467
- **Category**: Disabled feature / waiting on external dependency
- **Priority**: Low
- **Description**: The bus fullness filter UI (a `<select>` dropdown for "Empty", "Half-Full", "Full") is entirely commented out with an explanation that CTA Bus Tracker API currently returns empty strings for the `psgld` (passenger load) field. The backend code in `cta_client.py` normalizes and filters on this field, but the frontend has no way to expose the filter until CTA populates it. The dead code takes up ~15 lines and requires a comment to explain why it's disabled.
- **Suggested Improvement**: Delete the commented-out code block entirely. Document the condition ("Bus Tracker psgld field is empty; re-enable when CTA populates it") in a brief comment on line 454 or as a note in a project README. When CTA enables the data, restore the feature from git history or commit history.

---
