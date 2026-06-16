# Features Week of 2026-06-15

Last updated: 2026-06-15

## Completed

### AI Chat History and Sessions

- Replaced temporary in-memory chat history with SQLite-backed persistence in `chat/chat.db`.
- Persisted chat history by user and session so conversations survive page refreshes and app restarts.
- Added chat session browsing in the `Chats` panel so earlier conversations can be reopened and continued.
- Added device-level user identity support and `/name` handling so the assistant can remember the user on the same device.
- Added PDF export for saved chat conversations.

### Chat Window Controls

- Moved the existing chat header action buttons to the left side of the chat header.
- Added a top-right maximize/restore button to the chat window.
- Maximize expands the chat window to a fullscreen-style view below the app header and top bar.
- Re-pressing the maximize button restores the default popup size and position.
- The resize handle remains available in normal mode and is hidden while maximized.

### Cross-Session Memory Phase A

- Added Phase A same-user cross-session memory retrieval for the AI chat.
- The model now receives the latest `20` messages from the active session as live conversation context.
- It also receives up to `40` lexically relevant prior messages pulled from the same user's recent other sessions.
- Cross-session retrieval uses SQLite-backed lexical ranking over recent sessions rather than embeddings or external vector memory.
- Retrieval now prefers whole-term matches to avoid false positives from substring collisions such as `elev` inside `relevant`.
- Added SQLite indexes for session recency and message lookup to support the new retrieval path.
- Added console debug logging for cross-session search query normalization, extracted terms, candidate hits, and the final memory context passed to the LLM.
- Refactored the lexical retriever into `chat/lexical_search.py` with explicit raw DB-hit logging and selected memory-pair logging.
- Added typo-aware term expansion from recent same-user vocabulary so queries like `eliv` can surface `elev` evidence from prior sessions.
- Re-ranked memory pairs so definition-like corrected answers can outrank repeated typo-echo sessions.
- Added definition-query cleanup so once a resolved acronym/definition answer exists, stale non-definition chat history is dropped from cross-session memory.
- Added a structured "Resolved same-user memory for this query" summary block so typo-to-term carryover is explicit before the raw supporting history.
- Strengthened the LLM memory directive to treat resolved same-user memory as the preferred answer path unless current-session or data context overrides it.
- Cleaned cross-session context for typo/acronym follow-ups so stale negations like "not a term" do not contaminate the current answer when a prior resolved definition exists.

## Notes

- Keep appending new feature updates here as work lands during the week of 2026-06-15.
