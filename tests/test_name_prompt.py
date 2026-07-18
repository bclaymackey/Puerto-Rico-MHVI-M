"""Name-on-first-chat support: name_prompted flag helpers (mongodb.chat_dal).

Runs against the isolated test database; auth signup creates the user, then we
exercise the name-prompt flag the chat flow uses to ask the name exactly once.
"""

import pytest

from auth.core import signup
from mongodb import chat_dal

pytestmark = pytest.mark.usefixtures("mongo_test_db")


def test_new_account_has_not_been_name_prompted():
    user, _ = signup("tom@example.com", "secret@1")
    assert chat_dal.get_name_prompted(user["userId"]) is False


def test_set_name_prompted_marks_it_true():
    user, _ = signup("tom@example.com", "secret@1")
    chat_dal.set_name_prompted(user["userId"])
    assert chat_dal.get_name_prompted(user["userId"]) is True


def test_get_name_prompted_none_user_is_false():
    assert chat_dal.get_name_prompted(None) is False
