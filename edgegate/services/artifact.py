"""
Artifact service.

Manages model and evidence bundle artifacts with:
- Content-addressed storage (SHA-256)
- Artifact upload and retrieval
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, BinaryIO
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.db.models import (
    Artifact,
    ArtifactKind,
    Workspace,
    User,
    AuditEvent,
)


# ============================================================================
# Exceptions
# ============================================================================


class ArtifactError(Exception):
    """Base exception for Artifact operations."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ArtifactNotFoundError(ArtifactError):
    """Raised when Artifact is not found."""

    def __init__(self, artifact_id: UUID):
        super().__init__(f"Artifact {artifact_id} not found")
        self.artifact_id = artifact_id


class ArtifactSizeLimitError(ArtifactError):
    """Raised when artifact exceeds size limit."""

    def __init__(self, size: int, limit: int):
        super().__init__(f"Artifact size {size} exceeds limit {limit}")
        self.size = size
        self.limit = limit


# ============================================================================
# Response Types
# ============================================================================


@dataclass
class ArtifactInfo:
    """Artifact information for API responses."""
    id: UUID
    kind: ArtifactKind
    sha256: str
    size_bytes: int
    original_filename: Optional[str]
    storage_url: str
    created_at: datetime
    expires_at: Optional[datetime]


# ============================================================================
# Artifact Service
# ============================================================================


class ArtifactService:
    """
    Service for managing artifacts.
    
    Artifacts are stored with content-addressing (SHA-256).
    """

    # Size limits in bytes
    MAX_MODEL_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
    MAX_BUNDLE_SIZE = 10 * 1024 * 1024  # 10 MB

    def __init__(self, session: AsyncSession):
        self.session = session
        from edgegate.core import get_settings
        self.settings = get_settings()
        self.storage_dir = Path("./data/artifacts")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    async def create(
        self,
        workspace: Workspace,
        kind: ArtifactKind,
        content: bytes,
        original_filename: Optional[str] = None,
        user: Optional[User] = None,
    ) -> ArtifactInfo:
        """
        Create a new artifact from content.
        
        Args:
            workspace: The workspace.
            kind: Artifact type.
            content: Raw artifact content.
            original_filename: Original filename (optional).
            user: User uploading (optional).
            
        Returns:
            ArtifactInfo with created details.
            
        Raises:
            ArtifactSizeLimitError: If content exceeds size limit.
        """
        size = len(content)
        
        # Check size limits
        if kind == ArtifactKind.MODEL and size > self.MAX_MODEL_SIZE:
            raise ArtifactSizeLimitError(size, self.MAX_MODEL_SIZE)
        if kind == ArtifactKind.BUNDLE and size > self.MAX_BUNDLE_SIZE:
            raise ArtifactSizeLimitError(size, self.MAX_BUNDLE_SIZE)

        # Compute SHA-256
        sha256 = hashlib.sha256(content).hexdigest()

        # Check if artifact with same hash exists (dedup)
        existing = await self._get_by_sha256(workspace.id, sha256)
        if existing:
            return ArtifactInfo(
                id=existing.id,
                kind=existing.kind,
                sha256=existing.sha256,
                size_bytes=existing.size_bytes,
                original_filename=existing.original_filename,
                storage_url=existing.storage_url,
                created_at=existing.created_at,
                expires_at=existing.expires_at,
            )

        # Store content
        if self.settings.storage_backend == "s3":
            storage_url = await self._upload_to_s3(sha256, content)
        else:
            # Store content in local storage
            storage_path = self.storage_dir / sha256
            storage_path.write_bytes(content)
            storage_url = f"file://{storage_path.absolute()}"

        # Create artifact record
        artifact = Artifact(
            workspace_id=workspace.id,
            kind=kind,
            storage_url=storage_url,
            sha256=sha256,
            size_bytes=size,
            original_filename=original_filename,
        )
        self.session.add(artifact)

        # Audit event
        if user:
            await self._audit_event(
                workspace_id=workspace.id,
                user_id=user.id,
                event_type="artifact.created",
                event_json={
                    "kind": kind.value,
                    "sha256": sha256,
                    "size_bytes": size,
                    "filename": original_filename,
                },
            )

        await self.session.flush()

        return ArtifactInfo(
            id=artifact.id,
            kind=artifact.kind,
            sha256=artifact.sha256,
            size_bytes=artifact.size_bytes,
            original_filename=artifact.original_filename,
            storage_url=artifact.storage_url,
            created_at=artifact.created_at,
            expires_at=artifact.expires_at,
        )

    async def get(
        self,
        workspace: Workspace,
        artifact_id: UUID,
    ) -> ArtifactInfo:
        """
        Get artifact info.
        
        Args:
            workspace: The workspace.
            artifact_id: Artifact UUID.
            
        Returns:
            ArtifactInfo.
            
        Raises:
            ArtifactNotFoundError: If not found.
        """
        artifact = await self._get_artifact(workspace.id, artifact_id)
        if not artifact:
            raise ArtifactNotFoundError(artifact_id)

        return ArtifactInfo(
            id=artifact.id,
            kind=artifact.kind,
            sha256=artifact.sha256,
            size_bytes=artifact.size_bytes,
            original_filename=artifact.original_filename,
            storage_url=artifact.storage_url,
            created_at=artifact.created_at,
            expires_at=artifact.expires_at,
        )

    async def download(
        self,
        workspace: Workspace,
        artifact_id: UUID,
    ) -> bytes:
        """
        Download artifact content.
        
        Args:
            workspace: The workspace.
            artifact_id: Artifact UUID.
            
        Returns:
            Raw bytes.
            
        Raises:
            ArtifactNotFoundError: If not found.
        """
        artifact = await self._get_artifact(workspace.id, artifact_id)
        if not artifact:
            raise ArtifactNotFoundError(artifact_id)
            
        if artifact.storage_url.startswith("file://"):
            path = Path(artifact.storage_url.replace("file://", ""))
            if path.exists():
                return path.read_bytes()
        elif artifact.storage_url.startswith("s3://"):
            return await self._download_from_s3(artifact.storage_url)
                
        raise ArtifactError(f"Storage URL {artifact.storage_url} not accessible")

    async def _upload_to_s3(self, sha256: str, content: bytes) -> str:
        """Upload content to S3 and return s3:// URL."""
        import boto3
        import asyncio
        
        s3 = boto3.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url,
            aws_access_key_id=self.settings.s3_access_key_id,
            aws_secret_access_key=self.settings.s3_secret_access_key,
            region_name=self.settings.s3_region,
        )
        
        bucket = self.settings.s3_bucket_name
        key = f"artifacts/{sha256}"
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: s3.put_object(Bucket=bucket, Key=key, Body=content)
        )
        
        return f"s3://{bucket}/{key}"

    async def _download_from_s3(self, storage_url: str) -> bytes:
        """Download content from S3."""
        import boto3
        import asyncio
        
        # Parse s3://bucket/key
        parts = storage_url.replace("s3://", "").split("/", 1)
        if len(parts) != 2:
            raise ArtifactError(f"Invalid S3 URL: {storage_url}")
        bucket, key = parts
        
        s3 = boto3.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url,
            aws_access_key_id=self.settings.s3_access_key_id,
            aws_secret_access_key=self.settings.s3_secret_access_key,
            region_name=self.settings.s3_region,
        )
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: s3.get_object(Bucket=bucket, Key=key)
        )
        
        return response["Body"].read()

    async def get_by_sha256(
        self,
        workspace: Workspace,
        sha256: str,
    ) -> Optional[ArtifactInfo]:
        """
        Get artifact by SHA-256 hash.
        
        Args:
            workspace: The workspace.
            sha256: Content hash.
            
        Returns:
            ArtifactInfo if found, None otherwise.
        """
        artifact = await self._get_by_sha256(workspace.id, sha256)
        if not artifact:
            return None

        return ArtifactInfo(
            id=artifact.id,
            kind=artifact.kind,
            sha256=artifact.sha256,
            size_bytes=artifact.size_bytes,
            original_filename=artifact.original_filename,
            storage_url=artifact.storage_url,
            created_at=artifact.created_at,
            expires_at=artifact.expires_at,
        )

    async def list_all(
        self,
        workspace: Workspace,
        kind: Optional[ArtifactKind] = None,
    ) -> list[ArtifactInfo]:
        """
        List all artifacts in a workspace.
        
        Args:
            workspace: The workspace.
            kind: Filter by artifact type (optional).
            
        Returns:
            List of ArtifactInfo.
        """
        from typing import List
        
        query = select(Artifact).where(Artifact.workspace_id == workspace.id)
        
        if kind:
            query = query.where(Artifact.kind == kind)
        
        query = query.order_by(Artifact.created_at.desc())
        
        result = await self.session.execute(query)
        artifacts = result.scalars().all()
        
        return [
            ArtifactInfo(
                id=a.id,
                kind=a.kind,
                sha256=a.sha256,
                size_bytes=a.size_bytes,
                original_filename=a.original_filename,
                storage_url=a.storage_url,
                created_at=a.created_at,
                expires_at=a.expires_at,
            )
            for a in artifacts
        ]

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _get_artifact(
        self,
        workspace_id: UUID,
        artifact_id: UUID,
    ) -> Optional[Artifact]:
        """Get an Artifact by workspace and ID."""
        result = await self.session.execute(
            select(Artifact).where(
                and_(
                    Artifact.workspace_id == workspace_id,
                    Artifact.id == artifact_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _get_by_sha256(
        self,
        workspace_id: UUID,
        sha256: str,
    ) -> Optional[Artifact]:
        """Get an Artifact by workspace and SHA-256."""
        result = await self.session.execute(
            select(Artifact).where(
                and_(
                    Artifact.workspace_id == workspace_id,
                    Artifact.sha256 == sha256,
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
