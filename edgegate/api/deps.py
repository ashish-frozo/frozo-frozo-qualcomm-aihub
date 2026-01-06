"""
FastAPI dependencies for authentication and authorization.

Provides:
- get_current_user: Extract user from JWT token
- get_current_active_user: Ensure user is active
- get_workspace_with_role: Check workspace membership and role
"""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.db import get_session, WorkspaceRole
from edgegate.db.models import User, Workspace, WorkspaceMembership
from edgegate.services.auth import (
    AuthService,
    InvalidTokenError,
    TokenExpiredError,
    UserNotFoundError,
    UserInactiveError,
)
from edgegate.services.workspace import (
    WorkspaceService,
    WorkspaceAccessDeniedError,
    WorkspaceNotFoundError,
    InsufficientPermissionsError,
)


# Security scheme
bearer_scheme = HTTPBearer(auto_error=False)


# ============================================================================
# User Dependencies
# ============================================================================


async def get_current_user(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials],
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """
    Get the current authenticated user from the JWT token.
    
    Raises:
        HTTPException 401: If token is missing, invalid, or expired.
        HTTPException 401: If user is not found or inactive.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service = AuthService(session)

    try:
        user = await auth_service.get_current_user(credentials.credentials)
        return user
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (UserNotFoundError, UserInactiveError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )


# Type alias for current user dependency
CurrentUser = Annotated[User, Depends(get_current_user)]


# ============================================================================
# Workspace Dependencies
# ============================================================================


class WorkspaceChecker:
    """
    Dependency factory for workspace access checking with minimum role.
    
    Usage:
        @app.get("/workspaces/{workspace_id}/settings")
        async def get_settings(
            workspace: Annotated[Workspace, Depends(WorkspaceChecker(WorkspaceRole.ADMIN))]
        ):
            ...
    """

    def __init__(self, minimum_role: Optional[WorkspaceRole] = None):
        """
        Initialize the workspace checker.
        
        Args:
            minimum_role: Minimum role required (None = any role).
        """
        self.minimum_role = minimum_role

    async def __call__(
        self,
        workspace_id: UUID,
        current_user: CurrentUser,
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> Workspace:
        """
        Check workspace access and return workspace.
        
        Raises:
            HTTPException 404: If workspace not found.
            HTTPException 403: If access denied or insufficient permissions.
        """
        workspace_service = WorkspaceService(session)

        try:
            workspace = await workspace_service.get_workspace(workspace_id, current_user)

            # Check minimum role if specified
            if self.minimum_role:
                user_role = await workspace_service.get_user_role(workspace_id, current_user)
                if not self._has_minimum_role(user_role):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Requires {self.minimum_role.value} role",
                    )

            return workspace

        except WorkspaceNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        except WorkspaceAccessDeniedError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to workspace",
            )
        except InsufficientPermissionsError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=e.message,
            )

    def _has_minimum_role(self, user_role: Optional[WorkspaceRole]) -> bool:
        """Check if user has at least the minimum required role."""
        if user_role is None:
            return False

        role_hierarchy = {
            WorkspaceRole.OWNER: 3,
            WorkspaceRole.ADMIN: 2,
            WorkspaceRole.VIEWER: 1,
        }

        return role_hierarchy.get(user_role, 0) >= role_hierarchy.get(self.minimum_role, 0)


# Pre-configured workspace checkers
require_workspace_viewer = WorkspaceChecker(WorkspaceRole.VIEWER)
require_workspace_admin = WorkspaceChecker(WorkspaceRole.ADMIN)
require_workspace_owner = WorkspaceChecker(WorkspaceRole.OWNER)


# Type aliases for common patterns
WorkspaceViewer = Annotated[Workspace, Depends(require_workspace_viewer)]
WorkspaceAdmin = Annotated[Workspace, Depends(require_workspace_admin)]
WorkspaceOwner = Annotated[Workspace, Depends(require_workspace_owner)]


# ============================================================================
# Session Dependency (re-export for convenience)
# ============================================================================

DbSession = Annotated[AsyncSession, Depends(get_session)]
