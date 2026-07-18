# Puerto-Rico-MHVI-M
AIM-AHEAD Project with Grupo Nexos. The goal of this project is to 1) based on literature review, design a Mental Health Vulnerability Index for Minors in Puerto Rico (PR MHVI-M) &amp; 2) develop and deploy an interactive, dynamic dashboard that allows users to explore the data used to calculate the index.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python MHVIM_Dashboard_App.py
```

```bash
cd /Users/sreekanthgopi/desktop/Maria/Puerto-Rico-MHVI-M-final-version
source .venv/bin/activate
python MHVIM_Dashboard_App.py
```

Open http://127.0.0.1:8050.

## Chat history

Chat data is stored in `chat/chat.db`.

- `/new` clears the messages in the current session and starts a blank chat.
- `/session` starts a new session while preserving the previous session.
- `Chats` lists saved sessions and restores the selected conversation.
- `/name Tom` saves a preferred name for this browser device.
- Press `Enter` or click the send button to send a message.
- The LLM receives only the most recent 20 messages from the current session.
- Other sessions are persisted, but are not searched or included in LLM context.

Check the running server:

```bash
curl -I http://127.0.0.1:8050/
curl http://127.0.0.1:8050/_dash-layout
```

Inspect the chat database:

```bash
sqlite3 chat/chat.db ".tables"
sqlite3 -header -column chat/chat.db \
  "SELECT id, user_id, created_at FROM sessions ORDER BY created_at DESC;"
sqlite3 -header -column chat/chat.db \
  "SELECT id, session_id, role, content, timestamp FROM messages ORDER BY id;"
```
