"""MongoDB backend for the chat database.

Modular home for everything Mongo-related:
- client.py    connection, collections, integer id counter, index setup
- chat_dal.py  ported chat data-access functions (users / sessions / messages)
- migrate.py   one-time SQLite (chat/chat.db) -> MongoDB ETL

The dashboard database (pr_dashboard.db) is unrelated and stays on SQLite.
"""
