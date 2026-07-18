"""Email normalization and validation (auth.core)."""

from auth.core import normalize_email, valid_email


def test_normalize_lowercases_and_strips():
    assert normalize_email("  Tom@Example.COM  ") == "tom@example.com"


def test_normalize_handles_none():
    assert normalize_email(None) == ""


def test_valid_email_accepts_normal_address():
    assert valid_email("tom@example.com") is True


def test_valid_email_rejects_missing_at():
    assert valid_email("tom.example.com") is False


def test_valid_email_rejects_missing_domain_dot():
    assert valid_email("tom@example") is False


def test_valid_email_rejects_empty():
    assert valid_email("") is False
