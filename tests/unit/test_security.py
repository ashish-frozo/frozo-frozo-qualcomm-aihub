"""
Unit tests for security module.

Tests cover:
- Envelope encryption and decryption
- Ed25519 signing and verification
- HMAC computation and verification
- CI request verification
- Token utilities
"""

import base64
import os
import secrets
import tempfile
import time
from pathlib import Path

import pytest

from edgegate.core.security import (
    LocalKeyManagementService,
    compute_hmac,
    compute_sha256,
    compute_sha256_file,
    envelope_decrypt,
    envelope_encrypt,
    get_token_last4,
    redact_token,
    verify_ci_request,
    verify_hmac,
)


@pytest.fixture
def master_key_b64():
    """Generate a base64-encoded 32-byte master key."""
    return base64.b64encode(secrets.token_bytes(32)).decode()


@pytest.fixture
def temp_signing_keys_dir(tmp_path):
    """Temporary directory for signing keys."""
    return tmp_path / "signing_keys"


@pytest.fixture
def local_kms(master_key_b64, temp_signing_keys_dir):
    """Create a LocalKeyManagementService instance."""
    return LocalKeyManagementService(
        master_key_b64=master_key_b64,
        signing_keys_path=temp_signing_keys_dir,
    )


class TestLocalKMS:
    """Tests for LocalKeyManagementService."""

    def test_init_creates_signing_key(self, local_kms, temp_signing_keys_dir):
        """Test that initialization creates a signing key."""
        key_id = local_kms.key_id()
        assert key_id.startswith("key-v")

        # Check files were created
        key_files = list(temp_signing_keys_dir.glob("*.key.enc"))
        pub_files = list(temp_signing_keys_dir.glob("*.pub"))
        assert len(key_files) == 1
        assert len(pub_files) == 1

    def test_init_requires_master_key(self, temp_signing_keys_dir):
        """Test that empty master key raises error."""
        with pytest.raises(ValueError, match="Master key is required"):
            LocalKeyManagementService(
                master_key_b64="",
                signing_keys_path=temp_signing_keys_dir,
            )

    def test_init_requires_32_byte_key(self, temp_signing_keys_dir):
        """Test that non-32-byte master key raises error."""
        short_key = base64.b64encode(b"short").decode()
        with pytest.raises(ValueError, match="32 bytes"):
            LocalKeyManagementService(
                master_key_b64=short_key,
                signing_keys_path=temp_signing_keys_dir,
            )


class TestKeyWrapping:
    """Tests for DEK wrapping and unwrapping."""

    def test_wrap_unwrap_roundtrip(self, local_kms):
        """Test that wrapping and unwrapping returns original key."""
        dek = secrets.token_bytes(32)
        wrapped = local_kms.wrap_key(dek)
        unwrapped = local_kms.unwrap_key(wrapped)
        assert unwrapped == dek

    def test_wrapped_is_different(self, local_kms):
        """Test that wrapped key is different from original."""
        dek = secrets.token_bytes(32)
        wrapped = local_kms.wrap_key(dek)
        assert wrapped != dek

    def test_wrapped_contains_nonce(self, local_kms):
        """Test that wrapped key contains nonce (at least longer than DEK)."""
        dek = secrets.token_bytes(32)
        wrapped = local_kms.wrap_key(dek)
        # Should be at least 12 (nonce) + 32 (dek) + 16 (tag) = 60 bytes
        assert len(wrapped) >= 60


class TestSigning:
    """Tests for Ed25519 signing and verification."""

    def test_sign_verify_roundtrip(self, local_kms):
        """Test that signing and verification works."""
        data = b"Test data to sign"
        key_id, signature = local_kms.sign(data)

        assert key_id == local_kms.key_id()
        assert len(signature) == 64  # Ed25519 signature is 64 bytes
        assert local_kms.verify(data, signature, key_id)

    def test_verify_fails_with_wrong_data(self, local_kms):
        """Test that verification fails with modified data."""
        data = b"Original data"
        key_id, signature = local_kms.sign(data)

        assert not local_kms.verify(b"Modified data", signature, key_id)

    def test_verify_fails_with_wrong_signature(self, local_kms):
        """Test that verification fails with wrong signature."""
        data = b"Test data"
        key_id, _ = local_kms.sign(data)

        wrong_signature = bytes(64)
        assert not local_kms.verify(data, wrong_signature, key_id)

    def test_verify_fails_with_unknown_key_id(self, local_kms):
        """Test that verification fails with unknown key ID."""
        data = b"Test data"
        _, signature = local_kms.sign(data)

        assert not local_kms.verify(data, signature, "unknown-key-id")

    def test_get_public_key(self, local_kms):
        """Test that public key can be retrieved."""
        key_id = local_kms.key_id()
        public_key = local_kms.get_public_key(key_id)

        assert public_key is not None
        assert len(public_key) == 32  # Ed25519 public key is 32 bytes

    def test_rotate_signing_key(self, local_kms):
        """Test that key rotation creates new key."""
        import time
        old_key_id = local_kms.key_id()
        time.sleep(1)  # Ensure timestamp changes
        new_key_id = local_kms.rotate_signing_key()

        assert new_key_id != old_key_id
        assert local_kms.key_id() == new_key_id

        # Old signatures should still verify
        data = b"Test data"
        _, signature = local_kms.sign(data)
        assert local_kms.verify(data, signature, new_key_id)


class TestEnvelopeEncryption:
    """Tests for envelope encryption."""

    def test_encrypt_decrypt_roundtrip(self, local_kms):
        """Test that encryption and decryption works."""
        plaintext = b"Secret API token: abc123xyz"
        encrypted = envelope_encrypt(plaintext, local_kms)
        decrypted = envelope_decrypt(encrypted, local_kms)

        assert decrypted == plaintext

    def test_encrypted_is_different(self, local_kms):
        """Test that encrypted data is different from plaintext."""
        plaintext = b"Secret data"
        encrypted = envelope_encrypt(plaintext, local_kms)

        assert encrypted != plaintext
        assert plaintext not in encrypted

    def test_encrypted_format(self, local_kms):
        """Test that encrypted blob has expected format."""
        plaintext = b"Test data"
        encrypted = envelope_encrypt(plaintext, local_kms)

        # Format: wrapped_dek_len (2 bytes) + wrapped_dek + nonce (12 bytes) + ciphertext
        wrapped_len = int.from_bytes(encrypted[:2], "big")
        assert wrapped_len > 0
        assert len(encrypted) > 2 + wrapped_len + 12

    def test_decrypt_fails_with_wrong_kms(self, local_kms, master_key_b64, tmp_path):
        """Test that decryption fails with different KMS."""
        plaintext = b"Secret data"
        encrypted = envelope_encrypt(plaintext, local_kms)

        # Create new KMS with different master key
        other_key = base64.b64encode(secrets.token_bytes(32)).decode()
        other_kms = LocalKeyManagementService(
            master_key_b64=other_key,
            signing_keys_path=tmp_path / "other_keys",
        )

        with pytest.raises(Exception):
            envelope_decrypt(encrypted, other_kms)


class TestHMAC:
    """Tests for HMAC utilities."""

    def test_compute_hmac(self):
        """Test HMAC computation."""
        secret = b"my_secret_key"
        message = b"message to authenticate"
        hmac_value = compute_hmac(secret, message)

        assert len(hmac_value) == 64  # SHA-256 hex is 64 chars
        assert hmac_value.islower()  # Lowercase hex

    def test_verify_hmac_valid(self):
        """Test HMAC verification with valid signature."""
        secret = b"my_secret_key"
        message = b"message to authenticate"
        hmac_value = compute_hmac(secret, message)

        assert verify_hmac(secret, message, hmac_value)

    def test_verify_hmac_invalid(self):
        """Test HMAC verification with invalid signature."""
        secret = b"my_secret_key"
        message = b"message to authenticate"

        assert not verify_hmac(secret, message, "invalid_signature")

    def test_verify_hmac_wrong_message(self):
        """Test HMAC verification fails with wrong message."""
        secret = b"my_secret_key"
        message = b"original message"
        hmac_value = compute_hmac(secret, message)

        assert not verify_hmac(secret, b"modified message", hmac_value)


class TestCIRequestVerification:
    """Tests for CI request verification."""

    def test_valid_request(self):
        """Test verification of valid CI request."""
        secret = b"ci_secret"
        timestamp = int(time.time())
        nonce = secrets.token_hex(16)
        body = b'{"pipeline_id": "abc123"}'

        message = f"{timestamp}:{nonce}:".encode() + body
        signature = compute_hmac(secret, message)

        is_valid, error = verify_ci_request(
            secret, timestamp, nonce, body, signature
        )
        assert is_valid
        assert error == ""

    def test_stale_timestamp(self):
        """Test rejection of stale timestamp."""
        secret = b"ci_secret"
        timestamp = int(time.time()) - 600  # 10 minutes ago
        nonce = secrets.token_hex(16)
        body = b'{"pipeline_id": "abc123"}'

        message = f"{timestamp}:{nonce}:".encode() + body
        signature = compute_hmac(secret, message)

        is_valid, error = verify_ci_request(
            secret, timestamp, nonce, body, signature
        )
        assert not is_valid
        assert "timestamp" in error.lower()

    def test_future_timestamp(self):
        """Test rejection of future timestamp."""
        secret = b"ci_secret"
        timestamp = int(time.time()) + 600  # 10 minutes in future
        nonce = secrets.token_hex(16)
        body = b'{"pipeline_id": "abc123"}'

        message = f"{timestamp}:{nonce}:".encode() + body
        signature = compute_hmac(secret, message)

        is_valid, error = verify_ci_request(
            secret, timestamp, nonce, body, signature
        )
        assert not is_valid
        assert "timestamp" in error.lower()

    def test_invalid_signature(self):
        """Test rejection of invalid signature."""
        secret = b"ci_secret"
        timestamp = int(time.time())
        nonce = secrets.token_hex(16)
        body = b'{"pipeline_id": "abc123"}'

        is_valid, error = verify_ci_request(
            secret, timestamp, nonce, body, "invalid_signature"
        )
        assert not is_valid
        assert "signature" in error.lower()


class TestHashingUtilities:
    """Tests for hashing utilities."""

    def test_compute_sha256(self):
        """Test SHA-256 computation."""
        data = b"test data"
        hash_value = compute_sha256(data)

        assert len(hash_value) == 64
        assert hash_value.islower()

    def test_compute_sha256_deterministic(self):
        """Test that SHA-256 is deterministic."""
        data = b"same data"
        hash1 = compute_sha256(data)
        hash2 = compute_sha256(data)

        assert hash1 == hash2

    def test_compute_sha256_file(self, tmp_path):
        """Test SHA-256 computation for file."""
        file_path = tmp_path / "test.txt"
        file_path.write_bytes(b"file content")

        hash_value = compute_sha256_file(file_path)
        expected = compute_sha256(b"file content")

        assert hash_value == expected


class TestTokenUtilities:
    """Tests for token utilities."""

    def test_get_token_last4(self):
        """Test getting last 4 characters of token."""
        token = "abc123xyz789"
        assert get_token_last4(token) == "z789"

    def test_get_token_last4_short(self):
        """Test last4 with short token."""
        token = "ab"
        assert get_token_last4(token) == "**"

    def test_redact_token(self):
        """Test token redaction."""
        token = "abc123xyz789"
        redacted = redact_token(token)

        assert redacted.startswith("ab")
        assert redacted.endswith("z789")
        assert "*" in redacted
        assert token not in redacted

    def test_redact_token_short(self):
        """Test redaction of short token."""
        token = "short"
        redacted = redact_token(token)

        assert "*" in redacted
        assert token not in redacted
