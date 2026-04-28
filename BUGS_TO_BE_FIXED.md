# Bugs To Be Fixed

Known issues catalogued for future fixing. Severity: 🔴 High · 🟡 Medium · 🟢 Low.

> **Process:** When a bug in this file is fixed, **delete its entry from this file** and add a corresponding entry to the **Bugs Fixed** section of [`RESOLVED_HISTORY.md`](RESOLVED_HISTORY.md) documenting what was changed and how. This file should only ever contain bugs that have not yet been resolved.

---

## BUG-007 · Transit photos missing from production

- **File**: `frontend/public/transit-photos/` (directory), `frontend/src/App.jsx` (`PHOTOS` array)
- **Severity**: Low

**What happens:** The `frontend/public/transit-photos/` directory contains no image files. The app references photos like `blue-line-ohare.jpg` which return 404 on production, showing broken images in the background photo feature. This is a pre-existing asset gap from Phase 6 setup, not a code bug.

**Fix:** Add ≥10 transit photos to `frontend/public/transit-photos/` and update the `PHOTOS` array in `frontend/src/App.jsx` to match the filenames. Then commit and let Vercel redeploy.

---

