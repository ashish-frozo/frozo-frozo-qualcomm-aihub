"""
CI authentication middleware.

Provides HMAC-SHA256 verification for CI requests with:
- Signature validation
- Timestamp validation (5-minute window)
- Nonce replay prevention
"""

import hmac
import hashlib
import time
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.db import get_session
from edgegate.db.models import Workspace
from edgegate.services.integration import IntegrationService
from edgegate.services.nonce import NonceService, NonceReplayError, NonceExpiredError
from edgegate.core import get_settings
from edgegate.core.security import LocalKeyManagementService


# ============================================================================
# Constants
# ============================================================================


# Maximum age of a request in seconds
MAX_REQUEST_AGE_SECONDS = 300  # 5 minutes

# HMAC signature header name
SIGNATURE_HEADER = "X-EdgeGate-Signature"
TIMESTAMP_HEADER = "X-EdgeGate-Timestamp"
NONCE_HEADER = "X-EdgeGate-Nonce"
WORKSPACE_HEADER = "X-EdgeGate-Workspace"


# ============================================================================
# HMAC Utilities
# ============================================================================


def compute_signature(
    secret: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> str:
    """
    Compute the HMAC-SHA256 signature for a CI request.
    
    Args:
        secret: The workspace signing secret.
        timestamp: ISO8601 timestamp.
        nonce: Unique request nonce.
        body: Request body bytes.
        
    Returns:
        Hex-encoded HMAC signature.
    """
    # Construct the message to sign
    message = f"{timestamp}\n{nonce}\n".encode() + body
    
    # Compute HMAC-SHA256
    signature = hmac.new(
        secret.encode(),
        message,
        hashlib.sha256,
    ).hexdigest()
    
    return signature


def verify_signature(
    secret: str,
    signature: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> bool:
    """
    Verify the HMAC-SHA256 signature of a CI request.
    
    Args:
        secret: The workspace signing secret.
        signature: The provided signature.
        timestamp: ISO8601 timestamp.
        nonce: Unique request nonce.
        body: Request body bytes.
        
    Returns:
        True if signature is valid.
    """
    expected = compute_signature(secret, timestamp, nonce, body)
    return hmac.compare_digest(signature, expected)


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    Parse an ISO8601 timestamp.
    
    Args:
        timestamp_str: ISO8601 timestamp string.
        
    Returns:
        datetime object.
        
    Raises:
        ValueError: If timestamp is invalid.
    """
    # Handle both Z suffix and +00:00
    if timestamp_str.endswith('Z'):
        timestamp_str = timestamp_str[:-1] + '+00:00'
    
    return datetime.fromisoformat(timestamp_str)


def validate_timestamp(timestamp: datetime, max_age_seconds: int = MAX_REQUEST_AGE_SECONDS) -> bool:
    """
    Validate that a timestamp is within the allowed window.
    
    Args:
        timestamp: The request timestamp.
        max_age_seconds: Maximum age in seconds.
        
    Returns:
        True if timestamp is valid.
    """
    now = datetime.now(timezone.utc)
    
    # Check if timestamp is in the future (with small tolerance)
    if timestamp > now + timezone.utc.utcoffset(now) + timezone.utc.utcoffset(now):
        # Allow up to 30 seconds in the future for clock skew
        if (timestamp - now).total_seconds() > 30:
            return False
    
    # Check if timestamp is too old
    age = (now - timestamp).total_seconds()
    if age > max_age_seconds:
        return False
    
    return True


# ============================================================================
# FastAPI Dependencies
# ============================================================================


async def get_ci_workspace(
    request: Request,
    workspace_id: str = Header(..., alias=WORKSPACE_HEADER),
    signature: str = Header(..., alias=SIGNATURE_HEADER),
    timestamp: str = Header(..., alias=TIMESTAMP_HEADER),
    nonce: str = Header(..., alias=NONCE_HEADER),
    session: AsyncSession = Depends(get_session),
) -> Workspace:
    """
    FastAPI dependency for CI-authenticated requests.
    
    Validates:
    1. HMAC signature
    2. Timestamp (5-minute window)
    3. Nonce (replay prevention)
    
    Returns:
        The authenticated workspace.
        
    Raises:
        HTTPException: If authentication fails.
    """
    settings = get_settings()
    kms = LocalKeyManagementService(
        master_key_b64=settings.edgegenai_master_key,
        signing_keys_path=settings.signing_keys_dir,
    )
    
    # Parse workspace ID
    try:
        ws_id = UUID(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace ID",
        )
    
    # Get workspace
    from sqlalchemy import select
    result = await session.execute(
        select(Workspace).where(Workspace.id == ws_id)
    )
    workspace = result.scalar_one_or_none()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    
    # Validate timestamp
    try:
        ts = parse_timestamp(timestamp)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid timestamp format",
        )
    
    if not validate_timestamp(ts):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Request timestamp is stale or in the future",
        )
    
    # Get the signing secret for this workspace
    # Check if workspace has a CI secret configured
    if workspace.ci_secret_hash:
        # Decrypt the stored secret for HMAC verification
        import base64
        try:
            encrypted_bytes = base64.b64decode(workspace.ci_secret_hash.encode())
            signing_secret = kms.unwrap_key(encrypted_bytes).decode()
        except Exception:
            # If decryption fails, fall back to derived secret
            signing_secret = hmac.new(
                settings.edgegenai_master_key.encode(),
                str(workspace.id).encode(),
                hashlib.sha256,
            ).hexdigest()
    else:
        # Fallback: derive secret from workspace ID (for workspaces without CI secret)
        signing_secret = hmac.new(
            settings.edgegenai_master_key.encode(),
            str(workspace.id).encode(),
            hashlib.sha256,
        ).hexdigest()
    
    # Get request body
    body = await request.body()
    
    # Verify signature
    if not verify_signature(signing_secret, signature, timestamp, nonce, body):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )
    
    # Validate nonce (replay prevention)
    nonce_service = NonceService(session)
    try:
        # First check if nonce exists, if not create and consume it
        await nonce_service.validate_and_consume(ws_id, nonce)
    except NonceReplayError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nonce has already been used (replay detected)",
        )
    except NonceExpiredError:
        # If nonce doesn't exist, create it for future use
        # This allows clients to generate their own nonces
        # as long as they're unique within the window
        from edgegate.db.models import CINonce
        from datetime import timedelta
        
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=MAX_REQUEST_AGE_SECONDS)
        
        # CINonce model: nonce (pk), workspace_id, used_at, expires_at
        nonce_record = CINonce(
            nonce=nonce,
            workspace_id=ws_id,
            expires_at=expires_at,
            # used_at has server_default=func.now()
        )
        session.add(nonce_record)
        try:
            await session.flush()
        except Exception:
            # Nonce might already exist (race condition) - that's ok
            pass
    
    return workspace


# Type alias for dependency injection
CIWorkspace = Workspace
