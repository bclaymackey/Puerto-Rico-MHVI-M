"""Password rules and hashing (auth.core)."""

from auth.core import hash_password, validate_password, verify_password


def test_rejects_password_shorter_than_8():
    assert validate_password("a@1b") == "Password must be at least 8 characters."


def test_rejects_password_without_special_char():
    assert (
        validate_password("abcdefgh")
        == "Password must contain at least one special character (e.g. @)."
    )


def test_rejects_password_over_72_bytes():
    # 73 ASCII chars, includes a special char and is well over 8 — only the byte cap fails it.
    long_pw = "@" + "a" * 72
    assert validate_password(long_pw) == "Password is too long."


def test_accepts_valid_password():
    assert validate_password("secret@1") is None


def test_hash_then_verify_roundtrips():
    hashed = hash_password("secret@1")
    assert hashed != "secret@1"          # never store plaintext
    assert verify_password("secret@1", hashed) is True


def test_verify_rejects_wrong_password():
    hashed = hash_password("secret@1")
    assert verify_password("wrong@9", hashed) is False


def test_verify_handles_malformed_hash_gracefully():
    assert verify_password("secret@1", "not-a-real-bcrypt-hash") is False


def test_two_hashes_of_same_password_differ():
    # bcrypt salts each hash, so equal passwords produce different digests.
    assert hash_password("secret@1") != hash_password("secret@1")
