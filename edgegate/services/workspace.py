"""
Workspace service.

Provides CRUD operations for workspaces with:
- Workspace creation (auto-adds owner)
- Membership management (RBAC)
- Multi-tenancy enforcement
"""

from __future__ import annotations

from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from edgegate.db.models import (
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    User,
)


# ============================================================================
# Exceptions
# ============================================================================


class WorkspaceError(Exception):
    """Base exception for workspace operations."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class WorkspaceNotFoundError(WorkspaceError):
    """Raised when workspace is not found."""

    def __init__(self, workspace_id: UUID):
        super().__init__(f"Workspace {workspace_id} not found")
        self.workspace_id = workspace_id


class WorkspaceAccessDeniedError(WorkspaceError):
    """Raised when user doesn't have access to workspace."""

    def __init__(self, workspace_id: UUID, user_id: UUID):
        super().__init__(f"Access denied to workspace {workspace_id}")
        self.workspace_id = workspace_id
        self.user_id = user_id


class InsufficientPermissionsError(WorkspaceError):
    """Raised when user doesn't have required role."""

    def __init__(self, required_role: WorkspaceRole, actual_role: WorkspaceRole):
        super().__init__(
            f"Requires {required_role.value} role, but user has {actual_role.value}"
        )
        self.required_role = required_role
        self.actual_role = actual_role


class MembershipExistsError(WorkspaceError):
    """Raised when membership already exists."""

    def __init__(self, user_id: UUID, workspace_id: UUID):
        super().__init__(f"User {user_id} is already a member of workspace {workspace_id}")


class CannotRemoveOwnerError(WorkspaceError):
    """Raised when attempting to remove the last owner."""

    def __init__(self):
        super().__init__("Cannot remove the last owner from workspace")


# ============================================================================
# Workspace Service
# ============================================================================


class WorkspaceService:
    """
    Workspace service for workspace and membership management.
    
    All methods enforce multi-tenancy - users can only access
    workspaces they are members of.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ========================================================================
    # Workspace CRUD
    # ========================================================================

    async def create_workspace(
        self,
        name: str,
        owner: User,
    ) -> Workspace:
        """
        Create a new workspace with the given user as owner.
        
        Args:
            name: Workspace name.
            owner: User who will be the workspace owner.
            
        Returns:
            The created Workspace object.
        """
        workspace = Workspace(name=name)
        self.session.add(workspace)
        await self.session.flush()

        # Add owner membership
        membership = WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=owner.id,
            role=WorkspaceRole.OWNER,
        )
        self.session.add(membership)
        await self.session.flush()

        return workspace

    async def get_workspace(
        self,
        workspace_id: UUID,
        user: User,
    ) -> Workspace:
        """
        Get a workspace by ID, enforcing access control.
        
        Args:
            workspace_id: The workspace UUID.
            user: The requesting user (must be a member).
            
        Returns:
            The Workspace object.
            
        Raises:
            WorkspaceNotFoundError: If workspace doesn't exist.
            WorkspaceAccessDeniedError: If user is not a member.
        """
        # Check membership
        membership = await self._get_membership(workspace_id, user.id)
        if not membership:
            # Check if workspace exists to provide correct error
            workspace = await self._get_workspace_by_id(workspace_id)
            if not workspace:
                raise WorkspaceNotFoundError(workspace_id)
            raise WorkspaceAccessDeniedError(workspace_id, user.id)

        return membership.workspace

    async def list_workspaces(self, user: User) -> List[Workspace]:
        """
        List all workspaces the user is a member of.
        
        Args:
            user: The requesting user.
            
        Returns:
            List of Workspace objects.
        """
        result = await self.session.execute(
            select(Workspace)
            .join(WorkspaceMembership)
            .where(WorkspaceMembership.user_id == user.id)
            .options(selectinload(Workspace.memberships))
        )
        return list(result.scalars().all())

    async def update_workspace(
        self,
        workspace_id: UUID,
        user: User,
        name: Optional[str] = None,
    ) -> Workspace:
        """
        Update a workspace (requires admin or owner role).
        
        Args:
            workspace_id: The workspace UUID.
            user: The requesting user.
            name: New workspace name (optional).
            
        Returns:
            The updated Workspace object.
            
        Raises:
            InsufficientPermissionsError: If user is viewer.
        """
        membership = await self._require_role(
            workspace_id, user.id, WorkspaceRole.ADMIN
        )
        workspace = membership.workspace

        if name is not None:
            workspace.name = name

        await self.session.flush()
        return workspace

    async def delete_workspace(
        self,
        workspace_id: UUID,
        user: User,
    ) -> None:
        """
        Delete a workspace (requires owner role).
        
        Args:
            workspace_id: The workspace UUID.
            user: The requesting user.
            
        Raises:
            InsufficientPermissionsError: If user is not owner.
        """
        await self._require_role(workspace_id, user.id, WorkspaceRole.OWNER)

        workspace = await self._get_workspace_by_id(workspace_id)
        if workspace:
            await self.session.delete(workspace)
            await self.session.flush()

    # ========================================================================
    # Membership Management
    # ========================================================================

    async def add_member(
        self,
        workspace_id: UUID,
        user_to_add: User,
        role: WorkspaceRole,
        requesting_user: User,
    ) -> WorkspaceMembership:
        """
        Add a member to a workspace (requires admin or owner role).
        
        Args:
            workspace_id: The workspace UUID.
            user_to_add: User to add as member.
            role: Role to assign.
            requesting_user: User making the request.
            
        Returns:
            The created WorkspaceMembership object.
            
        Raises:
            InsufficientPermissionsError: If requesting user lacks permission.
            MembershipExistsError: If user is already a member.
        """
        # Only owners can add other owners
        required_role = WorkspaceRole.OWNER if role == WorkspaceRole.OWNER else WorkspaceRole.ADMIN
        await self._require_role(workspace_id, requesting_user.id, required_role)

        # Check if already a member
        existing = await self._get_membership(workspace_id, user_to_add.id)
        if existing:
            raise MembershipExistsError(user_to_add.id, workspace_id)

        membership = WorkspaceMembership(
            workspace_id=workspace_id,
            user_id=user_to_add.id,
            role=role,
        )
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def update_member_role(
        self,
        workspace_id: UUID,
        user_to_update: User,
        new_role: WorkspaceRole,
        requesting_user: User,
    ) -> WorkspaceMembership:
        """
        Update a member's role (requires owner role).
        
        Args:
            workspace_id: The workspace UUID.
            user_to_update: User whose role to update.
            new_role: New role to assign.
            requesting_user: User making the request.
            
        Returns:
            The updated WorkspaceMembership object.
            
        Raises:
            InsufficientPermissionsError: If requesting user is not owner.
            CannotRemoveOwnerError: If this would remove the last owner.
        """
        await self._require_role(workspace_id, requesting_user.id, WorkspaceRole.OWNER)

        membership = await self._get_membership(workspace_id, user_to_update.id)
        if not membership:
            raise WorkspaceAccessDeniedError(workspace_id, user_to_update.id)

        # Check if this would remove the last owner
        if membership.role == WorkspaceRole.OWNER and new_role != WorkspaceRole.OWNER:
            owner_count = await self._count_owners(workspace_id)
            if owner_count <= 1:
                raise CannotRemoveOwnerError()

        membership.role = new_role
        await self.session.flush()
        return membership

    async def remove_member(
        self,
        workspace_id: UUID,
        user_to_remove: User,
        requesting_user: User,
    ) -> None:
        """
        Remove a member from a workspace (requires owner role).
        
        Args:
            workspace_id: The workspace UUID.
            user_to_remove: User to remove.
            requesting_user: User making the request.
            
        Raises:
            InsufficientPermissionsError: If requesting user is not owner.
            CannotRemoveOwnerError: If this would remove the last owner.
        """
        await self._require_role(workspace_id, requesting_user.id, WorkspaceRole.OWNER)

        membership = await self._get_membership(workspace_id, user_to_remove.id)
        if not membership:
            return  # Already not a member

        # Check if this would remove the last owner
        if membership.role == WorkspaceRole.OWNER:
            owner_count = await self._count_owners(workspace_id)
            if owner_count <= 1:
                raise CannotRemoveOwnerError()

        await self.session.delete(membership)
        await self.session.flush()

    async def list_members(
        self,
        workspace_id: UUID,
        user: User,
    ) -> List[WorkspaceMembership]:
        """
        List all members of a workspace.
        
        Args:
            workspace_id: The workspace UUID.
            user: The requesting user (must be a member).
            
        Returns:
            List of WorkspaceMembership objects.
        """
        # Verify access
        await self._require_membership(workspace_id, user.id)

        result = await self.session.execute(
            select(WorkspaceMembership)
            .where(WorkspaceMembership.workspace_id == workspace_id)
            .options(selectinload(WorkspaceMembership.user))
        )
        return list(result.scalars().all())

    async def get_user_role(
        self,
        workspace_id: UUID,
        user: User,
    ) -> Optional[WorkspaceRole]:
        """
        Get a user's role in a workspace.
        
        Args:
            workspace_id: The workspace UUID.
            user: The user to check.
            
        Returns:
            WorkspaceRole or None if not a member.
        """
        membership = await self._get_membership(workspace_id, user.id)
        return membership.role if membership else None

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _get_workspace_by_id(self, workspace_id: UUID) -> Optional[Workspace]:
        """Get a workspace by ID without access control."""
        result = await self.session.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def _get_membership(
        self,
        workspace_id: UUID,
        user_id: UUID,
    ) -> Optional[WorkspaceMembership]:
        """Get a membership record."""
        result = await self.session.execute(
            select(WorkspaceMembership)
            .where(
                and_(
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.user_id == user_id,
                )
            )
            .options(selectinload(WorkspaceMembership.workspace))
        )
        return result.scalar_one_or_none()

    async def _require_membership(
        self,
        workspace_id: UUID,
        user_id: UUID,
    ) -> WorkspaceMembership:
        """Require that user is a member, raise if not."""
        membership = await self._get_membership(workspace_id, user_id)
        if not membership:
            raise WorkspaceAccessDeniedError(workspace_id, user_id)
        return membership

    async def _require_role(
        self,
        workspace_id: UUID,
        user_id: UUID,
        minimum_role: WorkspaceRole,
    ) -> WorkspaceMembership:
        """
        Require minimum role for an operation.
        
        Role hierarchy: OWNER > ADMIN > VIEWER
        """
        membership = await self._require_membership(workspace_id, user_id)

        role_hierarchy = {
            WorkspaceRole.OWNER: 3,
            WorkspaceRole.ADMIN: 2,
            WorkspaceRole.VIEWER: 1,
        }

        if role_hierarchy[membership.role] < role_hierarchy[minimum_role]:
            raise InsufficientPermissionsError(minimum_role, membership.role)

        return membership

    async def _count_owners(self, workspace_id: UUID) -> int:
        """Count number of owners in a workspace."""
        result = await self.session.execute(
            select(WorkspaceMembership)
            .where(
                and_(
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.role == WorkspaceRole.OWNER,
                )
            )
        )
        return len(result.scalars().all())
