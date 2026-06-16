# Chat Database Checks

Run these commands from the project directory.

## Check the server

```bash
curl -I http://127.0.0.1:8050/
curl http://127.0.0.1:8050/_dash-layout
```

## Check database tables

```bash
sqlite3 chat/chat.db ".tables"
```

## List users

```bash
sqlite3 -header -column chat/chat.db \
"SELECT * FROM users;"
```

## List sessions

```bash
sqlite3 -header -column chat/chat.db \
"SELECT id, user_id, created_at
 FROM sessions
 ORDER BY created_at DESC;"
```

## Count messages per session

```bash
sqlite3 -header -column chat/chat.db \
"SELECT session_id, COUNT(*) AS messages
 FROM messages
 GROUP BY session_id
 ORDER BY MAX(id) DESC;"
```

## List all messages

```bash
sqlite3 -header -column chat/chat.db \
"SELECT id, session_id, role, content, timestamp
 FROM messages
 ORDER BY id;"
```

## Show messages from the newest session

```bash
sqlite3 -header -column chat/chat.db \
"SELECT m.role, m.content, m.timestamp
 FROM messages AS m
 WHERE m.session_id = (
   SELECT id
   FROM sessions
   ORDER BY created_at DESC
   LIMIT 1
 )
 ORDER BY m.id;"
```

## Search messages by keyword

Replace `Tom` with the keyword you want to find.

```bash
sqlite3 -header -column chat/chat.db \
"SELECT id, session_id, role, content, timestamp
 FROM messages
 WHERE content LIKE '%SISW%' COLLATE NOCASE
 ORDER BY id;"
```

## Live chat history viewer

Run this in a third terminal:

```bash
cd /Users/sreekanthgopi/Desktop/Maria/Puerto-Rico-MHVI-M-final-version/
source .venv/bin/activate
python tools/chat_history_viewer.py
```

Open http://127.0.0.1:8060. The read-only viewer lists users and clickable
sessions and refreshes every two seconds as new chat messages are stored.
