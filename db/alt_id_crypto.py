"""Format-preserving encryption for [Contacts].[alt_id].

The alt_id column is encrypted at rest by the Alt-ID Encryptor tool
(Cathay_Scripts\\alt_id_hasher_worker.py). This module is a byte-exact
copy of that tool's cipher so the app can decrypt values for display
and encrypt user edits, given the session password.

Crypto spec (FROZEN — changing any constant breaks compatibility with
databases encrypted by the tool, and vice versa):
- Key: PBKDF2-HMAC-SHA256(password, salt=b"alt-id-fpe-v1", 200,000
  iterations), 32 bytes. Fixed salt on purpose: the same password must
  reproduce the same mapping on any machine, any run.
- Cipher: 10-round balanced Feistel over 32-bit values, halves of 16
  bits, round function HMAC-SHA256(key, round_byte + half)[0:2].
- Domain: [0, 2^31) — every ciphertext fits an Access Long Integer.
  Cycle-walking restricts the 2^32 bijection to the domain.

A WRONG password produces wrong-but-valid integers with no error —
nothing stored can detect it. Callers must surface that caveat in the
UI; the encryptor tool's timestamped backups are the recovery path.
"""

import hashlib
import hmac

DOMAIN = 1 << 31
ROUNDS = 10
FIXED_SALT = b"alt-id-fpe-v1"
PBKDF2_ITERATIONS = 200_000


def derive_key(password):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), FIXED_SALT, PBKDF2_ITERATIONS)


def _round(key, r, half):
    digest = hmac.new(
        key, r.to_bytes(1, "big") + half.to_bytes(4, "big"),
        hashlib.sha256).digest()
    return int.from_bytes(digest[:2], "big")


def _feistel_forward(key, value):
    left, right = value >> 16, value & 0xFFFF
    for r in range(ROUNDS):
        left, right = right, left ^ _round(key, r, right)
    return (left << 16) | right


def _feistel_backward(key, value):
    left, right = value >> 16, value & 0xFFFF
    for r in reversed(range(ROUNDS)):
        left, right = right ^ _round(key, r, left), left
    return (left << 16) | right


def _check_domain(value):
    value = int(value)
    if not 0 <= value < DOMAIN:
        raise ValueError(
            f"alt_id value {value} is outside [0, {DOMAIN - 1}]")
    return value


def encrypt_alt_id(key, value):
    value = _check_domain(value)
    value = _feistel_forward(key, value)
    while value >= DOMAIN:  # cycle-walk back into the domain
        value = _feistel_forward(key, value)
    return value


def decrypt_alt_id(key, value):
    value = _check_domain(value)
    value = _feistel_backward(key, value)
    while value >= DOMAIN:
        value = _feistel_backward(key, value)
    return value


# ── App-side helpers (not part of the frozen spec) ───────────────────


_key_cache = None  # (password, key) of the last derivation — PBKDF2 is slow


def cached_key(password):
    """The derived key for the session password, or None when the password
    is empty (feature off). Derives once (~0.15s) per distinct password."""
    global _key_cache
    if not password:
        return None
    if _key_cache is not None and _key_cache[0] == password:
        return _key_cache[1]
    key = derive_key(password)
    _key_cache = (password, key)
    return key


def decrypt_or_raw(key, value):
    """The decrypted value for display, or the value unchanged when there is
    no key, the value is None, or it is outside the domain. Never raises."""
    if key is None or value is None:
        return value
    try:
        return decrypt_alt_id(key, value)
    except (ValueError, TypeError):
        return value


def encrypt_or_raw(key, value):
    """Symmetric wrapper for the save path: encrypts when a key is set,
    passes through otherwise. Never raises."""
    if key is None or value is None:
        return value
    try:
        return encrypt_alt_id(key, value)
    except (ValueError, TypeError):
        return value
