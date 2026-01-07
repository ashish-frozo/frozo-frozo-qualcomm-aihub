"""
Security utilities for EdgeGate.

Includes:
- Envelope encryption (AES-256-GCM with wrapped DEK)
- Ed25519 signing and verification
- HMAC for CI endpoint authentication
- SHA-256 hashing utilities
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from nacl.encoding import RawEncoder
from nacl.signing import SigningKey, VerifyKey


# ============================================================================
# Key Management Service Interface
# ============================================================================


@runtime_checkable
class KeyManagementService(Protocol):
    """Protocol for key management operations."""

    def wrap_key(self, dek: bytes) -> bytes:
        """Wrap (encrypt) a data encryption key with the master key."""
        ...

    def unwrap_key(self, wrapped_dek: bytes) -> bytes:
        """Unwrap (decrypt) a data encryption key."""
        ...

    def sign(self, data: bytes) -> tuple[str, bytes]:
        """Sign data with the current signing key. Returns (key_id, signature)."""
        ...

    def verify(self, data: bytes, signature: bytes, key_id: str) -> bool:
        """Verify a signature with the specified key."""
        ...

    def key_id(self) -> str:
        """Get the current signing key ID."""
        ...


# ============================================================================
# Local KMS Implementation
# ============================================================================


class LocalKeyManagementService:
    """
    Local key management service using a master key from environment.
    
    Uses AES-256-GCM for envelope encryption and Ed25519 for signing.
    This is intended for local development and testing.
    """

    def __init__(
        self,
        master_key_b64: str,
        signing_keys_path: Path,
    ):
        """
        Initialize the local KMS.
        
        Args:
            master_key_b64: Base64-encoded 32-byte master key.
            signing_keys_path: Path to directory containing signing keys.
        """
        if not master_key_b64:
            raise ValueError("Master key is required (EDGEGENAI_MASTER_KEY)")

        # Add padding if missing and use urlsafe_b64decode
        padding = len(master_key_b64) % 4
        if padding:
            master_key_b64 += "=" * (4 - padding)
        
        try:
            self._master_key = base64.urlsafe_b64decode(master_key_b64)
        except Exception as e:
            raise ValueError(f"Invalid base64 master key: {e}")
        if len(self._master_key) != 32:
            raise ValueError("Master key must be exactly 32 bytes")

        self._aesgcm = AESGCM(self._master_key)
        self._signing_keys_path = signing_keys_path
        self._signing_keys: dict[str, SigningKey] = {}
        self._verify_keys: dict[str, VerifyKey] = {}
        self._current_key_id: str | None = None

        # Ensure signing keys directory exists
        self._signing_keys_path.mkdir(parents=True, exist_ok=True)

        # Load or create signing keys
        self._load_or_create_signing_key()

    def _load_or_create_signing_key(self) -> None:
        """Load existing signing keys or create a new one."""
        key_files = list(self._signing_keys_path.glob("*.key.enc"))

        if not key_files:
            # Create new signing key
            self._create_new_signing_key()
        else:
            # Load existing keys
            for key_file in sorted(key_files):
                key_id = key_file.stem.replace(".key", "")
                self._load_signing_key(key_id, key_file)

            # Set the latest key as current
            self._current_key_id = sorted(self._signing_keys.keys())[-1]

    def _create_new_signing_key(self) -> str:
        """Create and store a new signing key."""
        # Generate unique key ID
        timestamp = int(time.time())
        key_id = f"key-v{timestamp}"

        # Generate Ed25519 keypair
        signing_key = SigningKey.generate()

        # Encrypt the private key using envelope encryption
        encrypted = self._encrypt_data(signing_key.encode())

        # Save encrypted private key
        key_path = self._signing_keys_path / f"{key_id}.key.enc"
        key_path.write_bytes(encrypted)

        # Save public key (unencrypted, for verification)
        pub_path = self._signing_keys_path / f"{key_id}.pub"
        pub_path.write_bytes(signing_key.verify_key.encode())

        # Store in memory
        self._signing_keys[key_id] = signing_key
        self._verify_keys[key_id] = signing_key.verify_key
        self._current_key_id = key_id

        return key_id

    def _load_signing_key(self, key_id: str, key_path: Path) -> None:
        """Load an encrypted signing key."""
        encrypted = key_path.read_bytes()
        decrypted = self._decrypt_data(encrypted)
        signing_key = SigningKey(decrypted)
        self._signing_keys[key_id] = signing_key
        self._verify_keys[key_id] = signing_key.verify_key

    def _encrypt_data(self, plaintext: bytes) -> bytes:
        """Encrypt data using AES-256-GCM with a random nonce."""
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)
        return nonce + ciphertext

    def _decrypt_data(self, data: bytes) -> bytes:
        """Decrypt data encrypted with _encrypt_data."""
        nonce = data[:12]
        ciphertext = data[12:]
        return self._aesgcm.decrypt(nonce, ciphertext, None)

    def wrap_key(self, dek: bytes) -> bytes:
        """
        Wrap a data encryption key.
        
        The wrapped format is: nonce (12 bytes) + ciphertext
        """
        return self._encrypt_data(dek)

    def unwrap_key(self, wrapped_dek: bytes) -> bytes:
        """Unwrap a data encryption key."""
        return self._decrypt_data(wrapped_dek)

    def sign(self, data: bytes) -> tuple[str, bytes]:
        """
        Sign data with the current signing key.
        
        Returns:
            Tuple of (key_id, signature).
        """
        if self._current_key_id is None:
            raise RuntimeError("No signing key available")

        signing_key = self._signing_keys[self._current_key_id]
        signed = signing_key.sign(data, encoder=RawEncoder)
        return self._current_key_id, signed.signature

    def verify(self, data: bytes, signature: bytes, key_id: str) -> bool:
        """
        Verify a signature.
        
        Args:
            data: The original data that was signed.
            signature: The signature to verify.
            key_id: The key ID used for signing.
            
        Returns:
            True if signature is valid, False otherwise.
        """
        if key_id not in self._verify_keys:
            # Try to load public key from file
            pub_path = self._signing_keys_path / f"{key_id}.pub"
            if pub_path.exists():
                self._verify_keys[key_id] = VerifyKey(pub_path.read_bytes())
            else:
                return False

        try:
            self._verify_keys[key_id].verify(data, signature)
            return True
        except Exception:
            return False

    def key_id(self) -> str:
        """Get the current signing key ID."""
        if self._current_key_id is None:
            raise RuntimeError("No signing key available")
        return self._current_key_id

    def get_public_key(self, key_id: str) -> bytes | None:
        """Get the public key for a key ID."""
        if key_id in self._verify_keys:
            return self._verify_keys[key_id].encode()

        pub_path = self._signing_keys_path / f"{key_id}.pub"
        if pub_path.exists():
            return pub_path.read_bytes()

        return None

    def rotate_signing_key(self) -> str:
        """Create a new signing key and make it current."""
        return self._create_new_signing_key()


def sign_data(data: bytes, kms: KeyManagementService) -> tuple[str, str]:
    """
    Sign data and return (signature_b64, key_id).
    """
    key_id, signature = kms.sign(data)
    signature_b64 = base64.b64encode(signature).decode()
    return signature_b64, key_id


def verify_signature(
    data: bytes, signature_b64: str, key_id: str, kms: KeyManagementService
) -> bool:
    """
    Verify a base64-encoded signature.
    """
    try:
        signature = base64.b64decode(signature_b64)
        return kms.verify(data, signature, key_id)
    except Exception:
        return False


# ============================================================================
# Envelope Encryption
# ============================================================================


@dataclass
class EncryptedBlob:
    """Encrypted data with wrapped DEK."""

    wrapped_dek: bytes  # DEK encrypted with master key
    nonce: bytes  # 12-byte nonce for AES-GCM
    ciphertext: bytes  # Encrypted data

    def to_bytes(self) -> bytes:
        """Serialize to bytes: wrapped_dek_len (2 bytes) + wrapped_dek + nonce + ciphertext."""
        wrapped_len = len(self.wrapped_dek).to_bytes(2, "big")
        return wrapped_len + self.wrapped_dek + self.nonce + self.ciphertext

    @classmethod
    def from_bytes(cls, data: bytes) -> "EncryptedBlob":
        """Deserialize from bytes."""
        wrapped_len = int.from_bytes(data[:2], "big")
        wrapped_dek = data[2 : 2 + wrapped_len]
        nonce = data[2 + wrapped_len : 2 + wrapped_len + 12]
        ciphertext = data[2 + wrapped_len + 12 :]
        return cls(wrapped_dek=wrapped_dek, nonce=nonce, ciphertext=ciphertext)


def envelope_encrypt(plaintext: bytes, kms: KeyManagementService) -> bytes:
    """
    Encrypt data using envelope encryption.
    
    1. Generate random DEK
    2. Encrypt data with DEK
    3. Wrap DEK with master key
    4. Return wrapped_dek + nonce + ciphertext
    """
    # Generate random DEK
    dek = secrets.token_bytes(32)

    # Encrypt data with DEK
    aesgcm = AESGCM(dek)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    # Wrap DEK
    wrapped_dek = kms.wrap_key(dek)

    # Create blob
    blob = EncryptedBlob(wrapped_dek=wrapped_dek, nonce=nonce, ciphertext=ciphertext)
    return blob.to_bytes()


def envelope_decrypt(encrypted: bytes, kms: KeyManagementService) -> bytes:
    """
    Decrypt data using envelope encryption.
    
    1. Parse blob
    2. Unwrap DEK with master key
    3. Decrypt data with DEK
    """
    blob = EncryptedBlob.from_bytes(encrypted)

    # Unwrap DEK
    dek = kms.unwrap_key(blob.wrapped_dek)

    # Decrypt data
    aesgcm = AESGCM(dek)
    return aesgcm.decrypt(blob.nonce, blob.ciphertext, None)


# ============================================================================
# Hashing Utilities
# ============================================================================


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hash of data, return hex string."""
    return hashlib.sha256(data).hexdigest()


def compute_sha256_file(file_path: Path) -> str:
    """Compute SHA-256 hash of a file, return hex string."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_sha256_stream(stream) -> str:
    """Compute SHA-256 hash from a file-like object."""
    sha256 = hashlib.sha256()
    for chunk in iter(lambda: stream.read(8192), b""):
        sha256.update(chunk)
    return sha256.hexdigest()


# ============================================================================
# HMAC for CI Authentication
# ============================================================================


def compute_hmac(secret: bytes, message: bytes) -> str:
    """Compute HMAC-SHA256, return hex string."""
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_hmac(secret: bytes, message: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = compute_hmac(secret, message)
    return hmac.compare_digest(expected, signature)


def verify_ci_request(
    secret: bytes,
    timestamp: int,
    nonce: str,
    body: bytes,
    provided_signature: str,
    max_age_seconds: int = 300,
) -> tuple[bool, str]:
    """
    Verify CI request with timestamp + nonce + HMAC.
    
    Args:
        secret: Shared secret for HMAC.
        timestamp: Unix timestamp from request.
        nonce: Random nonce from request.
        body: Request body.
        provided_signature: Signature from request header.
        max_age_seconds: Maximum age of request (default 5 minutes).
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    # Check timestamp
    current_time = int(time.time())
    if abs(current_time - timestamp) > max_age_seconds:
        return False, "Request timestamp too old or in future"

    # Compute expected signature
    message = f"{timestamp}:{nonce}:".encode() + body
    if not verify_hmac(secret, message, provided_signature):
        return False, "Invalid signature"

    return True, ""


# ============================================================================
# Token Utilities
# ============================================================================


def get_token_last4(token: str) -> str:
    """Get last 4 characters of a token for display."""
    if len(token) < 4:
        return "*" * len(token)
    return token[-4:]


def redact_token(token: str) -> str:
    """Redact a token for safe logging."""
    if len(token) < 8:
        return "*" * len(token)
    return token[:2] + "*" * (len(token) - 6) + token[-4:]
