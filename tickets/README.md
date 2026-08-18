# Tickets — Operations Reference

## Admin UI

Visit **http://127.0.0.1:8050/tickets_ui** while logged in as an admin account.

> Your account must have `role: "admin"` in the `users` collection (see setup below).
> All other users are redirected to `/`.

Features:
- Filter by status: **All / Open / Responded / Closed**
- Write a reply and save, or close the ticket directly from the table

---

## Set an account to admin (one-time setup)

```bash
mongosh pr_chat
```

```js
// Replace the email with your admin account's email
db.users.updateOne(
  { email: "devananda1502@gmail.com" },
  { $set: { role: "admin" } }
)
```

---

## mongosh CLI quick reference

```bash
mongosh pr_chat
```

```js
// List all open tickets (newest first)
db.tickets.find({ status: "open" }).sort({ created_at: -1 }).pretty()

// List all tickets for a specific user
db.tickets.find({ email: "user@example.com" }).sort({ created_at: -1 }).pretty()

// Count by status
db.tickets.aggregate([{ $group: { _id: "$status", count: { $sum: 1 } } }])

// Mark a ticket as responded with a reply
db.tickets.updateOne(
  { _id: ObjectId("REPLACE_WITH_ID") },
  { $set: { status: "responded", reply: "Thanks, we are looking into this." } }
)

// Close a ticket
db.tickets.updateOne(
  { _id: ObjectId("REPLACE_WITH_ID") },
  { $set: { status: "closed" } }
)

// Delete a test ticket
db.tickets.deleteOne({ _id: ObjectId("REPLACE_WITH_ID") })
```

---

## Data model

```
tickets collection
  _id         ObjectId   auto-generated
  user_id     string     submitter's account id
  email       string     submitter's email (denormalized)
  category    string     Technical | Account | Data | Other
  subject     string     ≤ 120 chars
  message     string     ≤ 2000 chars
  status      string     open | responded | closed
  reply       string     admin reply text (set via UI or mongosh)
  created_at  datetime   UTC timestamp
```

---

## Future email notification

Add `tickets/notify.py` with `send_ticket_email(ticket)` using `smtplib`.
Wire it as one line in `tickets/core.py` → `create_ticket()` after a successful
insert. No UI, callback, or storage change required.
