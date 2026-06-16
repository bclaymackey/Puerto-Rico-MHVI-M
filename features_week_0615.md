# Features Week of 2026-06-15

Last updated: 2026-06-15

## Snapshot

- AI Chat History and Sessions
  - SQLite Storage: Persistent chat history in `chat/chat.db`.
  - Session Continuity: User and session state survive refreshes and restarts.
  - Saved Browsing: Reopen and continue earlier chat sessions.
  - Device Naming: Remember the user's name on the same device.
  - PDF Export: Export saved chat transcripts as PDF.
- Chat Window Controls
  - Left Actions: Chat header actions moved to the left side.
  - Maximize Toggle: Added maximize and restore controls.
  - Fullscreen Layout: Chat expands below the app header and top bar.
  - Resize Support: Resize handle stays in normal mode and hides when maximized.
- Cross-Session Memory Phase A
  - Live Context: Send the latest active-session messages to the model.
  - Lexical Retrieval: Pull relevant same-user history from recent sessions.
  - Typo Matching: Surface close matches like `eliv` to `elev`.
  - Memory Rerank: Prefer resolved definition-style answers over noisy repeats.
  - Context Cleanup: Drop stale negative memory when better resolved memory exists.
- Chat Sessions and UX
  - Language Memory: Remember the selected chat language in the same browser.
  - New Session: Start a fresh chat without overwriting saved sessions.
  - Session Titles: Auto-title, rename, and delete saved conversations.
  - History Search: Search chats by keyword and jump to matched messages.
  - Message Tools: Show timestamps and add copy actions for assistant replies.
  - Expanded Panel: Full-height Chats panel with theming and active-session highlighting.

Detailed notes follow below.

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

### Chat Sessions and UX

- Added browser-level language remember-me for the chat sign-on so the selected language can reopen automatically on the same browser.
- Added a dedicated `New Chat` button that starts a fresh session without overwriting saved conversations.
- Added automatic session titles from the first user message, plus custom session renaming support.
- Added conversation deletion support for removing unwanted saved sessions.
- Added session recency tracking with `updated_at` so saved conversations can sort by latest activity.
- Added chat history keyword search across saved conversations with direct session open and matched-message jump navigation.
- Added message timestamps inside chat conversations for both loaded history and new live messages.
- Added copy-to-clipboard actions for assistant replies.
- Refreshed the Chats panel into a full-height expandable browser with active-session highlighting, search, rename, and delete controls.
- Verified the chat session metadata flow with a local SQLite smoke test covering auto-title generation, rename, search, timestamps, and delete.

## Notes

- Keep appending new feature updates here as work lands during the week of 2026-06-15.
