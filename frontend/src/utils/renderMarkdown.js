/**
 * Strip common Markdown syntax so AI-generated text reads as plain prose.
 * Only removes formatting — does not sanitise HTML or handle nested structures.
 * @param {string} text
 * @returns {string}
 */
export function renderMarkdown(text) {
  return text
    .replace(/^#{1,3}\s+/gm, "")              // strip heading markers (# / ## / ###)
    .replace(/\*\*(.*?)\*\*/g, "$1")           // strip bold **text**
    .replace(/\*([^*]+)\*/g, "$1")             // strip italic *text*
    // NOTE: no _…_ italic rule — it would corrupt snake_case identifiers in
    // AI text (e.g. `max_users_count` → `maxuserscount`). LLM output uses
    // **bold** and *italic* almost exclusively; underscore-italics are rare
    // enough that the false-positive risk outweighs the formatting benefit.
    .replace(/`([^`]+)`/g, "$1")               // strip inline code `text`
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")   // strip link [label](url) → label
    .replace(/^[-*>]\s+/gm, "")               // strip bullet / blockquote markers
    .trim();
}
