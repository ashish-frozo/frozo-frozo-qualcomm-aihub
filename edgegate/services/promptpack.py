"""
PromptPack service.

Manages versioned collections of prompts with:
- Schema validation
- Immutability enforcement (no edits after creation)
- Canonicalization (LF, trim, JSON sort)
- SHA-256 content hashing
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.db.models import (
    PromptPack,
    Workspace,
    User,
    AuditEvent,
)
from edgegate.validators.promptpack import PromptPackValidator


# ============================================================================
# Exceptions
# ============================================================================


class PromptPackError(Exception):
    """Base exception for PromptPack operations."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class PromptPackNotFoundError(PromptPackError):
    """Raised when PromptPack is not found."""

    def __init__(self, promptpack_id: str, version: Optional[str] = None):
        if version:
            super().__init__(f"PromptPack {promptpack_id}@{version} not found")
        else:
            super().__init__(f"PromptPack {promptpack_id} not found")
        self.promptpack_id = promptpack_id
        self.version = version


class PromptPackExistsError(PromptPackError):
    """Raised when PromptPack version already exists."""

    def __init__(self, promptpack_id: str, version: str):
        super().__init__(f"PromptPack {promptpack_id}@{version} already exists")
        self.promptpack_id = promptpack_id
        self.version = version


class PromptPackValidationError(PromptPackError):
    """Raised when PromptPack validation fails."""

    def __init__(self, issues: List[Dict[str, Any]]):
        super().__init__("PromptPack validation failed")
        self.issues = issues


class PromptPackImmutableError(PromptPackError):
    """Raised when attempting to modify an immutable PromptPack."""

    def __init__(self, promptpack_id: str, version: str):
        super().__init__(f"PromptPack {promptpack_id}@{version} is immutable")
        self.promptpack_id = promptpack_id
        self.version = version


# ============================================================================
# Response Types
# ============================================================================


@dataclass
class PromptPackInfo:
    """PromptPack information for API responses."""
    id: UUID
    promptpack_id: str
    version: str
    sha256: str
    case_count: int
    published: bool
    created_at: datetime


@dataclass
class PromptPackDetail:
    """Full PromptPack details including content."""
    id: UUID
    promptpack_id: str
    version: str
    sha256: str
    json_content: Dict[str, Any]
    published: bool
    created_at: datetime


# ============================================================================
# Canonicalization
# ============================================================================


def canonicalize_promptpack(content: Dict[str, Any]) -> Dict[str, Any]:
    """
    Canonicalize PromptPack content for consistent hashing.
    
    Rules:
    1. Sort all keys alphabetically
    2. Normalize line endings to LF
    3. Trim whitespace from string values
    """
    def normalize_value(v: Any) -> Any:
        if isinstance(v, str):
            # Normalize line endings to LF and trim
            return v.replace('\r\n', '\n').replace('\r', '\n').strip()
        elif isinstance(v, dict):
            return {k: normalize_value(val) for k, val in sorted(v.items())}
        elif isinstance(v, list):
            return [normalize_value(item) for item in v]
        return v

    return normalize_value(content)


def compute_promptpack_sha256(content: Dict[str, Any]) -> str:
    """Compute SHA256 hash of canonicalized PromptPack content."""
    canonical = canonicalize_promptpack(content)
    json_str = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()


# ============================================================================
# PromptPack Service
# ============================================================================


class PromptPackService:
    """
    Service for managing PromptPacks.
    
    PromptPacks are immutable after creation. Each unique combination of
    workspace_id + promptpack_id + version can only be created once.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.validator = PromptPackValidator()

    async def create(
        self,
        workspace: Workspace,
        promptpack_id: str,
        version: str,
        content: Dict[str, Any],
        user: User,
    ) -> PromptPackInfo:
        """
        Create a new PromptPack version.
        
        Args:
            workspace: The workspace.
            promptpack_id: Unique identifier (e.g., "llama2-basic").
            version: Version string (e.g., "1.0.0").
            content: PromptPack JSON content.
            user: User creating the PromptPack.
            
        Returns:
            PromptPackInfo with created details.
            
        Raises:
            PromptPackValidationError: If content is invalid.
            PromptPackExistsError: If version already exists.
        """
        # Validate content
        result = self.validator.validate(content)
        if not result.valid:
            raise PromptPackValidationError([
                {"code": i.code, "message": i.message, "path": i.path}
                for i in result.issues
            ])

        # Check if version already exists
        existing = await self._get_promptpack(
            workspace.id, promptpack_id, version
        )
        if existing:
            raise PromptPackExistsError(promptpack_id, version)

        # Canonicalize and hash
        canonical = canonicalize_promptpack(content)
        sha256 = compute_promptpack_sha256(content)

        # Create PromptPack
        promptpack = PromptPack(
            workspace_id=workspace.id,
            promptpack_id=promptpack_id,
            version=version,
            sha256=sha256,
            json_content=canonical,
            published=False,
        )
        self.session.add(promptpack)

        # Audit event
        await self._audit_event(
            workspace_id=workspace.id,
            user_id=user.id,
            event_type="promptpack.created",
            event_json={
                "promptpack_id": promptpack_id,
                "version": version,
                "sha256": sha256,
                "case_count": len(content.get("cases", [])),
            },
        )

        await self.session.flush()

        return PromptPackInfo(
            id=promptpack.id,
            promptpack_id=promptpack_id,
            version=version,
            sha256=sha256,
            case_count=len(canonical.get("cases", [])),
            published=False,
            created_at=promptpack.created_at,
        )

    async def get(
        self,
        workspace: Workspace,
        promptpack_id: str,
        version: str,
    ) -> PromptPackDetail:
        """
        Get a specific PromptPack version.
        
        Args:
            workspace: The workspace.
            promptpack_id: PromptPack identifier.
            version: Version string.
            
        Returns:
            PromptPackDetail with full content.
            
        Raises:
            PromptPackNotFoundError: If not found.
        """
        promptpack = await self._get_promptpack(
            workspace.id, promptpack_id, version
        )
        if not promptpack:
            raise PromptPackNotFoundError(promptpack_id, version)

        return PromptPackDetail(
            id=promptpack.id,
            promptpack_id=promptpack_id,
            version=version,
            sha256=promptpack.sha256,
            json_content=promptpack.json_content,
            published=promptpack.published,
            created_at=promptpack.created_at,
        )

    async def list_versions(
        self,
        workspace: Workspace,
        promptpack_id: str,
    ) -> List[PromptPackInfo]:
        """
        List all versions of a PromptPack.
        
        Args:
            workspace: The workspace.
            promptpack_id: PromptPack identifier.
            
        Returns:
            List of PromptPackInfo for each version.
        """
        result = await self.session.execute(
            select(PromptPack)
            .where(
                and_(
                    PromptPack.workspace_id == workspace.id,
                    PromptPack.promptpack_id == promptpack_id,
                )
            )
            .order_by(PromptPack.created_at.desc())
        )
        packs = result.scalars().all()

        return [
            PromptPackInfo(
                id=p.id,
                promptpack_id=p.promptpack_id,
                version=p.version,
                sha256=p.sha256,
                case_count=len(p.json_content.get("cases", [])),
                published=p.published,
                created_at=p.created_at,
            )
            for p in packs
        ]

    async def list_all(
        self,
        workspace: Workspace,
    ) -> List[PromptPackInfo]:
        """
        List all PromptPacks in a workspace.
        
        Args:
            workspace: The workspace.
            
        Returns:
            List of PromptPackInfo for all PromptPacks.
        """
        result = await self.session.execute(
            select(PromptPack)
            .where(PromptPack.workspace_id == workspace.id)
            .order_by(PromptPack.promptpack_id, PromptPack.created_at.desc())
        )
        packs = result.scalars().all()

        return [
            PromptPackInfo(
                id=p.id,
                promptpack_id=p.promptpack_id,
                version=p.version,
                sha256=p.sha256,
                case_count=len(p.json_content.get("cases", [])),
                published=p.published,
                created_at=p.created_at,
            )
            for p in packs
        ]

    async def publish(
        self,
        workspace: Workspace,
        promptpack_id: str,
        version: str,
        user: User,
    ) -> PromptPackInfo:
        """
        Publish a PromptPack version (makes it available for pipelines).
        
        Args:
            workspace: The workspace.
            promptpack_id: PromptPack identifier.
            version: Version string.
            user: User publishing.
            
        Returns:
            Updated PromptPackInfo.
            
        Raises:
            PromptPackNotFoundError: If not found.
        """
        promptpack = await self._get_promptpack(
            workspace.id, promptpack_id, version
        )
        if not promptpack:
            raise PromptPackNotFoundError(promptpack_id, version)

        promptpack.published = True

        # Audit event
        await self._audit_event(
            workspace_id=workspace.id,
            user_id=user.id,
            event_type="promptpack.published",
            event_json={
                "promptpack_id": promptpack_id,
                "version": version,
                "sha256": promptpack.sha256,
            },
        )

        await self.session.flush()

        return PromptPackInfo(
            id=promptpack.id,
            promptpack_id=promptpack_id,
            version=version,
            sha256=promptpack.sha256,
            case_count=len(promptpack.json_content.get("cases", [])),
            published=True,
            created_at=promptpack.created_at,
        )

    async def delete(
        self,
        workspace: Workspace,
        promptpack_id: str,
        version: str,
        user: User,
    ) -> None:
        """
        Delete a PromptPack version (only unpublished).
        
        Args:
            workspace: The workspace.
            promptpack_id: PromptPack identifier.
            version: Version string.
            user: User deleting.
            
        Raises:
            PromptPackNotFoundError: If not found.
            PromptPackImmutableError: If published (cannot delete).
        """
        promptpack = await self._get_promptpack(
            workspace.id, promptpack_id, version
        )
        if not promptpack:
            raise PromptPackNotFoundError(promptpack_id, version)

        if promptpack.published:
            raise PromptPackImmutableError(promptpack_id, version)

        await self.session.delete(promptpack)

        # Audit event
        await self._audit_event(
            workspace_id=workspace.id,
            user_id=user.id,
            event_type="promptpack.deleted",
            event_json={
                "promptpack_id": promptpack_id,
                "version": version,
            },
        )

        await self.session.flush()

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _get_promptpack(
        self,
        workspace_id: UUID,
        promptpack_id: str,
        version: str,
    ) -> Optional[PromptPack]:
        """Get a PromptPack by workspace, id, and version."""
        result = await self.session.execute(
            select(PromptPack).where(
                and_(
                    PromptPack.workspace_id == workspace_id,
                    PromptPack.promptpack_id == promptpack_id,
                    PromptPack.version == version,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _audit_event(
        self,
        workspace_id: UUID,
        user_id: UUID,
        event_type: str,
        event_json: dict,
    ) -> None:
        """Create an audit event."""
        event = AuditEvent(
            workspace_id=workspace_id,
            actor_user_id=user_id,
            event_type=event_type,
            event_json=event_json,
        )
        self.session.add(event)
