"""Tests for db.alt_id_crypto — the frozen FPE used for [Contacts].[alt_id].

The constants and compatibility vectors pin wire compatibility with the
Alt-ID Encryptor tool (Cathay_Scripts\alt_id_hasher_worker.py): a database
encrypted by that tool must decrypt here with the same password.
"""

import pytest

from db import alt_id_crypto as crypto


@pytest.fixture(scope="module")
def key():
    return crypto.derive_key("test-pass")


def test_frozen_constants():
    assert crypto.DOMAIN == 1 << 31
    assert crypto.ROUNDS == 10
    assert crypto.FIXED_SALT == b"alt-id-fpe-v1"
    assert crypto.PBKDF2_ITERATIONS == 200_000


def test_compatibility_vectors(key):
    # Computed once with Cathay_Scripts\alt_id_hasher_worker.py — pins wire
    # compatibility with the encryptor tool, not just self-consistency.
    assert crypto.encrypt_alt_id(key, 12345) == 2013903282
    assert crypto.encrypt_alt_id(key, 0) == 592227195
    assert crypto.encrypt_alt_id(key, 2**31 - 1) == 1785344663


def test_round_trip_edge_values(key):
    for v in (0, 1, 65535, 65536, 12345, 999_999_999, 2**31 - 1):
        assert crypto.decrypt_alt_id(key, crypto.encrypt_alt_id(key, v)) == v


def test_out_of_domain_raises(key):
    for bad in (-1, 2**31):
        with pytest.raises(ValueError):
            crypto.encrypt_alt_id(key, bad)
        with pytest.raises(ValueError):
            crypto.decrypt_alt_id(key, bad)


def test_cached_key_empty_password_is_none():
    assert crypto.cached_key("") is None


def test_cached_key_derives_once_per_password(monkeypatch):
    calls = []
    real = crypto.derive_key
    monkeypatch.setattr(crypto, "derive_key",
                        lambda pw: calls.append(pw) or real(pw))
    crypto.cached_key("pw-a")
    crypto.cached_key("pw-a")
    assert calls == ["pw-a"]
    crypto.cached_key("pw-b")
    assert calls == ["pw-a", "pw-b"]


def test_decrypt_or_raw_pass_through(key):
    assert crypto.decrypt_or_raw(None, 123) == 123          # no key -> raw
    assert crypto.decrypt_or_raw(key, None) is None         # NULL passes
    assert crypto.decrypt_or_raw(key, 2**31 + 5) == 2**31 + 5  # out of domain
    cipher = crypto.encrypt_alt_id(key, 4321)
    assert crypto.decrypt_or_raw(key, cipher) == 4321


def test_encrypt_or_raw_pass_through(key):
    assert crypto.encrypt_or_raw(None, 123) == 123
    assert crypto.encrypt_or_raw(key, None) is None
    assert crypto.encrypt_or_raw(key, 4321) == crypto.encrypt_alt_id(key, 4321)


def test_wrong_key_gives_wrong_value(key):
    other = crypto.derive_key("test-pass-2")
    cipher = crypto.encrypt_alt_id(key, 4321)
    assert crypto.decrypt_or_raw(other, cipher) != 4321
