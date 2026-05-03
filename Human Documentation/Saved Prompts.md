# Saved Prompts

## Scoping Prompt

Your task is to complete scoping work needed for [X]. Document this as a new feature in docs/FEATURE_PLANS.md. Match the depth of existing entries — for complex features, split the work into separate chunks.

---

## Scoping Prompt from other LLM Research

Your task is to complete scoping work for the attached document, which captures ideas I developed with other LLMs and want to bring into this context. Review the document, identify each distinct feature or change, and scope each one out in docs/FEATURE_PLANS.md. After scoping a feature, delete it from the attached document. Focus only on lines [START]–[END]; ignore the rest for now.

---

## Feature / Efficiency / Tech Debt / Bug Fix Development

Use the `resolve-item` skill (`/resolve-item <ITEM-ID>`) — e.g. `/resolve-item BUG-042`, `/resolve-item OPT-007`, `/resolve-item TD-019`, `/resolve-item FEAT-031`. The skill handles implementation, doc updates, and verification.
