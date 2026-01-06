"""
Services package.
"""

from edgegate.services.auth import (
    AuthService,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    AuthenticationError,
    InvalidCredentialsError,
    TokenExpiredError,
    InvalidTokenError,
    UserNotFoundError,
    UserExistsError,
    UserInactiveError,
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from edgegate.services.workspace import (
    WorkspaceService,
    WorkspaceError,
    WorkspaceNotFoundError,
    WorkspaceAccessDeniedError,
    InsufficientPermissionsError,
    MembershipExistsError,
    CannotRemoveOwnerError,
)

__all__ = [
    # Auth
    "AuthService",
    "Token",
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "AuthenticationError",
    "InvalidCredentialsError",
    "TokenExpiredError",
    "InvalidTokenError",
    "UserNotFoundError",
    "UserExistsError",
    "UserInactiveError",
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    # Workspace
    "WorkspaceService",
    "WorkspaceError",
    "WorkspaceNotFoundError",
    "WorkspaceAccessDeniedError",
    "InsufficientPermissionsError",
    "MembershipExistsError",
    "CannotRemoveOwnerError",
]
