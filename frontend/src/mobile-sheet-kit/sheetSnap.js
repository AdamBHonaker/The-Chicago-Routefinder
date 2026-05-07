// Persist the user's most-recent manual sheet snap so the bottom sheet
// opens at their preferred height across sessions. Only manual settles
// (drag release) should write here — programmatic auto-promotes (route
// arrival, trip start) are deliberately not persisted; that decision lives
// in the host project.
//
// Factory pattern so the same kit can be embedded in multiple host
// projects, each with its own localStorage key (e.g. "crf:sheetSnap").

const VALID_SNAPS = [0, 1, 2];

function safeGet(key) {
  try {
    if (typeof localStorage === "undefined") return null;
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key, value) {
  try {
    if (typeof localStorage === "undefined") return false;
    localStorage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

// Returns { load, save } bound to a single localStorage key. Out-of-range
// or unparseable values load as null (silently treated as absent rather
// than thrown) so a future schema bump won't crash existing sessions.
export function createSheetSnapStore(storageKey) {
  if (typeof storageKey !== "string" || storageKey.length === 0) {
    throw new Error("createSheetSnapStore: storageKey is required");
  }
  return {
    load() {
      const raw = safeGet(storageKey);
      if (raw == null) return null;
      const n = parseInt(raw, 10);
      return VALID_SNAPS.includes(n) ? n : null;
    },
    save(idx) {
      if (!VALID_SNAPS.includes(idx)) return false;
      return safeSet(storageKey, String(idx));
    },
  };
}
