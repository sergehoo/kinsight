"""Chiffrement at-rest des secrets de connecteurs (tokens, mots de passe…).

`cryptography`/Fernet n'étant pas garanti dans tous les environnements, on implémente
un chiffrement authentifié **stdlib uniquement** : keystream HMAC-SHA256 (mode flux) +
encrypt-then-MAC (intégrité). Clé dérivée par PBKDF2 de `INTEGRATIONS_SECRET_KEY`.

PROD : remplacer par un gestionnaire de secrets (KMS/Vault) ou `cryptography` Fernet.
Aucune valeur n'est jamais renvoyée en clair par l'API (cf. serializers).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from django.conf import settings

_SALT = b"k-insight-integrations-v1"
_NONCE = 16
_TAG = 32


def _key() -> bytes:
    secret = getattr(settings, "INTEGRATIONS_SECRET_KEY", None) or settings.SECRET_KEY
    return hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), _SALT, 120_000, dklen=32)


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest())
        counter += 1
    return bytes(out[:length])


def encrypt(plaintext: str | None) -> str:
    if not plaintext:
        return ""
    key = _key()
    nonce = secrets.token_bytes(_NONCE)
    data = plaintext.encode("utf-8")
    ct = bytes(a ^ b for a, b in zip(data, _keystream(key, nonce, len(data))))
    tag = hmac.new(key, nonce + ct, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(nonce + tag + ct).decode("ascii")


def decrypt(token: str | None) -> str:
    if not token:
        return ""
    raw = base64.urlsafe_b64decode(token.encode("ascii"))
    nonce, tag, ct = raw[:_NONCE], raw[_NONCE : _NONCE + _TAG], raw[_NONCE + _TAG :]
    key = _key()
    expected = hmac.new(key, nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):
        raise ValueError("Secret altéré ou clé de chiffrement invalide.")
    pt = bytes(a ^ b for a, b in zip(ct, _keystream(key, nonce, len(ct))))
    return pt.decode("utf-8")


def mask(value: str | None) -> str:
    """Représentation masquée pour l'affichage (jamais le secret en clair)."""
    if not value:
        return ""
    return f"••••{value[-4:]}" if len(value) > 4 else "••••"
