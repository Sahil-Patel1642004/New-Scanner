from __future__ import annotations

import hashlib
import json
import secrets
from base64 import b64decode, b64encode, urlsafe_b64encode
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def _fernet_key() -> bytes:
    digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return urlsafe_b64encode(digest)


def _derive_licence_signing_private_key() -> Ed25519PrivateKey:
    seed = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return Ed25519PrivateKey.from_private_bytes(seed[:32])


def get_licence_signing_public_key() -> str:
    public_key = _derive_licence_signing_private_key().public_key()
    return b64encode(
        public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")


def sign_licence_payload(payload: Mapping[str, Any]) -> dict[str, str]:
    canonical_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
    signature = _derive_licence_signing_private_key().sign(canonical_payload)
    return {
        "signature": b64encode(signature).decode("ascii"),
        "public_key": get_licence_signing_public_key(),
    }


def verify_licence_signature(payload: Mapping[str, Any], signature_b64: str, public_key_b64: str | None = None) -> bool:
    public_key_data = public_key_b64 or get_licence_signing_public_key()
    try:
        public_key = Ed25519PublicKey.from_public_bytes(b64decode(public_key_data.encode("ascii")))
        signature_bytes = b64decode(signature_b64.encode("ascii"))
        canonical_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
        public_key.verify(signature_bytes, canonical_payload)
        return True
    except (ValueError, TypeError, InvalidSignature):
        return False


def encrypt_product_key(product_key: str) -> str:
    return Fernet(_fernet_key()).encrypt(product_key.encode("utf-8")).decode("utf-8")


def decrypt_product_key(ciphertext: str) -> str:
    return Fernet(_fernet_key()).decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def generate_product_key() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    groups = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4)]
    return f"SCANORA-{groups[0]}-{groups[1]}-{groups[2]}-{groups[3]}"


def hash_product_key(product_key: str) -> str:
    normalized = product_key.strip().upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def mask_product_key(product_key: str) -> str:
    visible = product_key[:12]
    return f"{visible}****"
