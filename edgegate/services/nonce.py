"""
Nonce service for CI replay prevention.

Provides:
- Nonce generation
- Nonce storage and validation
- Automatic expiration (5 minute window)
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.db.models import CINonce


# ============================================================================
# Exceptions
# ============================================================================


class NonceError(Exception):
    """Base exception for Nonce operations."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NonceReplayError(NonceError):
    """Raised when a nonce has already been used."""

    def __init__(self, nonce: str):
        super().__init__(f"Nonce has already been used: {nonce[:16]}...")
        self.nonce = nonce


class NonceExpiredError(NonceError):
    """Raised when a nonce has expired."""

    def __init__(self, nonce: str):
        super().__init__(f"Nonce has expired: {nonce[:16]}...")
        self.nonce = nonce


# ============================================================================
# Nonce Service
# ============================================================================


class NonceService:
    """
    Service for managing CI nonces.
    
    Nonces prevent replay attacks by ensuring each CI request
    can only be processed once within a 5-minute window.
    """

    # Nonce validity window
    NONCE_WINDOW_SECONDS = 300  # 5 minutes

    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate(self, workspace_id: UUID) -> str:
        """
        Generate a new nonce for a workspace.
        
        Args:
            workspace_id: The workspace UUID.
            
        Returns:
            The generated nonce string.
        """
        nonce = str(uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.NONCE_WINDOW_SECONDS)
        
        nonce_record = CINonce(
            workspace_id=workspace_id,
            nonce=nonce,
            created_at=now,
            expires_at=expires_at,
            used=False,
        )
        self.session.add(nonce_record)
        await self.session.flush()
        
        return nonce

    async def validate_and_consume(
        self,
        workspace_id: UUID,
        nonce: str,
    ) -> bool:
        """
        Validate and consume a nonce.
        
        Args:
            workspace_id: The workspace UUID.
            nonce: The nonce to validate.
            
        Returns:
            True if nonce is valid and was consumed.
            
        Raises:
            NonceReplayError: If nonce was already used.
            NonceExpiredError: If nonce has expired.
        """
        now = datetime.now(timezone.utc)
        
        # Look up the nonce
        result = await self.session.execute(
            select(CINonce).where(
                and_(
                    CINonce.workspace_id == workspace_id,
                    CINonce.nonce == nonce,
                )
            )
        )
        nonce_record = result.scalar_one_or_none()
        
        if nonce_record is None:
            # Nonce not found - could be expired or invalid
            raise NonceExpiredError(nonce)
        
        if nonce_record.used:
            raise NonceReplayError(nonce)
        
        if nonce_record.expires_at < now:
            raise NonceExpiredError(nonce)
        
        # Mark as used
        nonce_record.used = True
        await self.session.flush()
        
        return True

    async def cleanup_expired(self) -> int:
        """
        Remove expired nonces from the database.
        
        Returns:
            Number of nonces deleted.
        """
        now = datetime.now(timezone.utc)
        
        result = await self.session.execute(
            delete(CINonce).where(CINonce.expires_at < now)
        )
        await self.session.flush()
        
        return result.rowcount
