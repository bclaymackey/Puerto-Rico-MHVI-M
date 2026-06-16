# Plan: Persistent users / sessions / messages for the chat

## Context

The MHVI-M dashboard already has a **fully working** chat. Today its history
lives only in an in-memory pandas DataFrame (`chat_history_manager.py`) that is
wiped on every server restart, has no concept of a `user_id`, and never touches
disk. `session_id` is a fresh UUID per browser session (memory storage), so even
a page reload loses the thread.

The goal is to add real persistence backed by three tables —

```
users     (id, email)
sessions  (id, user_id, created_at)
messages  (id, session_id, role, content, timestamp)
```

— so each request stores the message, sends the **recent 20 messages** of that
session to the LLM as context, and returns the answer. Nothing currently working
should change behavior. Keep it lean: this is a simple chat over data, **not**
agentic.

### Decisions locked with the user
- **Separate `chat.db`** SQLite file (chat data isolated from `pr_dashboard.db`).
- **Anonymous persistent `user_id`**: a UUID held in the browser via a
  `dcc.Store` with `storage_type='local'` (survives reloads). A `users` row is
  created on first use; no login UI.
- **Last 20 messages** (combined user+assistant rows) sent to the LLM each turn.
- **Do NOT use `sqlite-memory`** (the vendored folder). It is a C extension for
  embeddings / vector + FTS5 semantic search aimed at agentic memory — massive
  overkill that would add a compiled dependency. Three plain SQL statements via
  the stdlib `sqlite3` module solve this. It would increase, not reduce, code.

### Why this approach
The cleanest change keeps `chat_history_manager.py` as the **single touchpoint**
for history. We swap its DataFrame internals for SQLite-backed reads/writes while
keeping the existing function signatures, so `ai_service.py` and `callbacks.py`
need only minimal, additive edits (threading `user_id` through). This honors
"don't drop anything already working."

---

## Changes

### 1. New file: `chat_db.py` (connection + schema)
A tiny module mirroring the style of `data.py:get_db_connection()`.

- `get_chat_db_connection()` → `sqlite3.connect(<dir>/chat.db)`.
- `init_chat_db()` → `CREATE TABLE IF NOT EXISTS` for the three tables:
  - `users(id TEXT PRIMARY KEY, email TEXT)`
  - `sessions(id TEXT PRIMARY KEY, user_id TEXT, created_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id))`
  - `messages(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT,
    role TEXT, content TEXT, timestamp TEXT,
    FOREIGN KEY(session_id) REFERENCES sessions(id))`
- Helper upserts used on first contact (idempotent, `INSERT OR IGNORE`):
  - `ensure_user(user_id, email=None)`
  - `ensure_session(session_id, user_id)` (sets `created_at = utcnow` on insert)

`init_chat_db()` is called once at startup from `MHVIM_Dashboard_App.py`
(next to `load_db_metadata()`).

### 2. Rewrite internals of `chat_history_manager.py` (keep signatures)
Reuse the existing public API so callers barely change. Replace the
`_history_df` global with SQLite calls into `chat_db.py`.

- `_append_row(session_id, role, content)` → `INSERT INTO messages ...`
  (keep the function; just change the body to an INSERT).
- `build_llm_context(session_id, user_message, max_turns=...)`:
  - Append the user message, then
    `SELECT role, content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT 20`
    and reverse to chronological. **Change the window to last 20 messages**
    (replace the current `tail(max_turns * 2)` logic). Returns the same
    `[{"role","content"}]` shape — `ai_service.call_llm` is unchanged.
- `save_ai_response(session_id, ai_message)` → INSERT assistant row (unchanged signature).
- `get_history_for_display(session_id)` → `SELECT role, content ... ORDER BY id`
  returning the same `[{"role","text"}]` shape (PDF export keeps working).
- `clear_session(session_id)` → `DELETE FROM messages WHERE session_id=?`.

New optional param threading: `build_llm_context` / the chat entry point need the
`user_id` so the session can be linked. Simplest: have `ai_service` call
`ensure_user`/`ensure_session` (see #3), keeping `chat_history_manager` focused
purely on messages.

### 3. `ai_service.py` — thread `user_id`, register session
- `process_chat_message(user_input, language="en", session_id="default",
  user_id=None)`: add the `user_id` param (default keeps backward compat).
- At the top of `process_chat_message`, call
  `ensure_user(user_id)` + `ensure_session(session_id, user_id)` once so the
  message INSERTs always have valid parent rows. All three existing branches
  (report / navigation / standard LLM) are otherwise untouched.

### 4. UI wiring — `layout.py` + `callbacks.py`
- `layout.py`: add one store
  `dcc.Store(id='chat-user-id', storage_type='local')` next to the existing
  `chat-session-id` store (line ~357). Persisting in `local` storage gives a
  stable anonymous user across reloads.
- A tiny clientside callback (or a normal callback) to **populate `chat-user-id`
  with a UUID if empty** on load — Dash pattern:
  `app.clientside_callback` writing `crypto.randomUUID()` when the store is null.
  (Session id can stay per-session as-is, or also be promoted to `local`; default:
  leave session_id as-is so each visit is a new session under the same user.)
- `callbacks.py:generate_ai_response`: add
  `State('chat-user-id', 'data')` and pass `user_id` into
  `process_chat_message(...)`. No other callback logic changes.

---

## Files touched
- `chat/chat_db.py`: schema, users, sessions, names, and session listing.
- `chat/chat_history_manager.py`: SQLite-backed message history.
- `chat/ai_service.py`: user/session registration and preferred-name lookup.
- `chat/llm_caller.py`: preferred-name instruction.
- `chat/__init__.py`: public chat API.
- `callbacks.py`: user ID, commands, session list/restoration, and Enter-to-send.
- `layout.py`: chat stores, `Chats` panel, and controls.
- `MHVIM_Dashboard_App.py`: initializes the chat database.
- `db_test.md` and `README.md`: run and verification instructions.
- `.gitignore`: excludes local environments, secrets, caches, and `chat/chat.db`.

## Reused existing code
- `data.py:get_db_connection()` pattern (mirror it for `chat.db`).
- `chat_history_manager.py` public functions (signatures preserved → callers stable).
- Existing `chat-session-id` `dcc.Store` and the `pending-user-message` flow.

---

## Verification (end-to-end)
1. Start the app: `python MHVIM_Dashboard_App.py` → confirm `chat/chat.db` is
   created with `users`, `sessions`, `messages`
   (`sqlite3 chat/chat.db ".tables"`).
2. Open the chat, send 3–4 messages. After each, confirm rows land in `messages`
   (`SELECT role, content FROM messages ORDER BY id`).
3. Reload the page → confirm `chat-user-id` (local storage) is unchanged, a **new**
   session row appears, and the old session's messages still exist on disk.
4. Send a follow-up that depends on earlier context (e.g. "and what about Ponce?")
   → confirm the LLM answer reflects prior turns (history is being sent).
5. Confirm only the **last 20** messages are passed: log/inspect the list returned
   by `build_llm_context` after >20 messages.
6. Regression: report request ("generate a report for Arecibo") and a navigation
   "how do I..." question both still work and still record to `messages`.
7. Restart the server → confirm history **persists** (the original in-memory bug
   is gone) and the chat PDF export still renders past messages.

---

## Implemented state

- Chat modules are organized under `chat/`.
- SQLite history is stored in `chat/chat.db`.
- A persistent anonymous `user_id` is stored in browser local storage.
- Each page visit starts with a new in-memory `session_id`.
- The LLM receives the latest 20 messages from the current session only.
- `/new` deletes the current session's messages and keeps the same session ID.
- `/session` switches to a new session ID and preserves the old session.
- `Chats` lists the device user's saved sessions; selecting one restores its
  complete UI history and makes it the active session for continued chatting.
- `/name Tom` stores `Tom` on the persistent device user and supplies that
  preferred name to the LLM in future sessions.
- The `users` table is migrated idempotently with a nullable `name` column.
- Preferred names allow letters, spaces, apostrophes, periods, and hyphens,
  and are limited to 80 characters.
- Pressing `Enter` in the chat input sends the message, matching the send button.
- Chat history browsing is consolidated in the dashboard `Chats` panel.
- Previous sessions remain in SQLite, but are not searched or sent to the LLM.
  Cross-session memory is not implemented.

### Latest files changed

- `chat/chat_db.py`: name migration, preferred-name helpers, session listing.
- `chat/llm_caller.py`: preferred-name instruction for the LLM.
- `chat/ai_service.py`: loads the device user's preferred name.
- `chat/__init__.py`: exports the new chat persistence helpers.
- `layout.py`: adds the `Chats` button and sessions panel.
- `callbacks.py`: lists/restores sessions and handles `/name`.
- `db_test.md`: database, search, and chat-control commands.

### Verification commands

```bash
curl -I http://127.0.0.1:8050/
curl http://127.0.0.1:8050/_dash-layout

sqlite3 chat/chat.db ".tables"
sqlite3 -header -column chat/chat.db \
  "SELECT id, name, email FROM users;"
sqlite3 -header -column chat/chat.db \
  "SELECT id, user_id, created_at FROM sessions ORDER BY created_at DESC;"
sqlite3 -header -column chat/chat.db \
  "SELECT session_id, COUNT(*) AS message_count FROM messages GROUP BY session_id ORDER BY MAX(id) DESC;"
sqlite3 -header -column chat/chat.db \
  "SELECT id, session_id, role, content, timestamp FROM messages ORDER BY id;"
sqlite3 -header -column chat/chat.db \
  "SELECT id, session_id, role, content FROM messages WHERE content LIKE '%Tom%' COLLATE NOCASE ORDER BY id;"
```

## Work completed today

Today we upgraded the dashboard’s AI chat from temporary in-memory history to
persistent, user-linked SQLite storage. We created users, sessions, and messages
tables in `chat/chat.db`, added automatic schema initialization, and stored a
anonymous user ID in browser local storage. Every conversation now has a
session ID, persists across server restarts, and supplies the latest twenty
messages from the active session to GPT-5 Nano.

We organized all chat-related Python modules under `chat/` and preserved the
existing report, navigation, PDF export, and dashboard behavior. We added
`/new` to clear the active conversation, `/session` to create a separate saved
conversation, and `/name Tom` to persist a preferred device-level name that is
included in future model instructions.

The dashboard now includes a scrollable `Chats` panel beside `Download PDF`.
It lists saved conversations with a title, date, time, and message count,
highlights the active session, and restores the selected conversation
so users can continue chatting. Pressing Enter now sends messages, matching the
send button.

We documented SQLite inspection and keyword-search commands, removed the
temporary standalone history viewer, cleared generated caches, and updated
`.gitignore` for secrets, virtual environments, and runtime chat data. Finally,
we verified Python parsing, SQLite integrity, database persistence, Dash layout,
and callback registration.
