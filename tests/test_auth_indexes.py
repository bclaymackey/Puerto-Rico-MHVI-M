"""Auth index provisioning tolerates the legacy anonymous users.

The real chat DB already holds anonymous user docs with `email: null` (browser-UUID
identities, pre-login). The unique email index must still build in their presence,
so it uses a partial filter (email is a string) rather than a plain unique index.
"""

import pytest

from auth.db import ensure_auth_indexes

pytestmark = pytest.mark.usefixtures("mongo_test_db")


def test_email_index_builds_with_preexisting_null_emails(mongo_test_db):
    # Simulate the real DB: several anonymous users, all with email == None.
    mongo_test_db.users.drop_indexes()
    mongo_test_db.users.insert_many([{"_id": f"anon-{i}", "email": None} for i in range(3)])

    # Must not raise DuplicateKeyError on the null emails.
    ensure_auth_indexes()

    # And it still enforces uniqueness among real (string) emails.
    mongo_test_db.users.insert_one({"email": "tom@example.com"})
    with pytest.raises(Exception):
        mongo_test_db.users.insert_one({"email": "tom@example.com"})
