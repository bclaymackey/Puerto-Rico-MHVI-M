"""CLI: create an admin account and re-key all anonymous chat history onto it.

The re-key logic lives in `auth.migrate` (pure + tested); this is only the runner.

Usage (from the project root):
    python -m mongodb.migrate_auth                 # DRY RUN — prints counts, writes nothing
    python -m mongodb.migrate_auth --apply         # perform the re-key

Environment (read at runtime, never committed):
    ADMIN_EMAIL      email for the admin account (default: admin@localhost)
    ADMIN_PASSWORD   password for the admin account (required for --apply)

Always back up first:
    mongodump --db pr_chat --out ./backup_$(date +%F)
"""

import os
import sys

from auth.migrate import ensure_admin, rekey_anonymous_to_admin


def main() -> None:
    apply = "--apply" in sys.argv
    email = os.getenv("ADMIN_EMAIL", "admin@localhost")

    if apply and not os.getenv("ADMIN_PASSWORD"):
        print("ERROR: set ADMIN_PASSWORD in the environment to run with --apply.")
        sys.exit(1)

    # In a dry run we don't want to create the admin either; use a placeholder id
    # so we can still count what *would* move.
    if apply:
        admin_id = ensure_admin(email, os.environ["ADMIN_PASSWORD"])
    else:
        from auth.db import get_users

        existing = get_users().find_one({"email": email.strip().lower()})
        admin_id = str(existing["_id"]) if existing else "0" * 24  # placeholder ObjectId

    result = rekey_anonymous_to_admin(admin_id, dry_run=not apply)

    print(f"admin_email        : {email}")
    print(f"admin_id           : {result['admin_id']}")
    print(f"anonymous_users    : {result['anon_users']}")
    print(f"sessions_to_rekey  : {result['sessions_rekeyed']}")
    print(f"applied            : {result['applied']}")
    if not apply:
        print("\n[dry run] nothing was written. Re-run with --apply to perform the re-key.")


if __name__ == "__main__":
    main()
