"""
Authentication service.

Provides JWT-based authentication with:
- User registration and login
- Password hashing with bcrypt
- JWT access token generation and validation
- Current user extraction from tokens
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.core import get_settings
from edgegate.db.models import User


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================================
# Schemas
# ============================================================================


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str  # User ID as string
    exp: datetime
    iat: datetime


class Token(BaseModel):
    """Authentication token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserCreate(BaseModel):
    """Schema for user registration."""

    email: EmailStr
    password: str


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response."""

    id: UUID
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Exceptions
# ============================================================================


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        self.message = message
        super().__init__(message)


class InvalidCredentialsError(AuthenticationError):
    """Raised when credentials are invalid."""

    def __init__(self):
        super().__init__("Invalid email or password")


class TokenExpiredError(AuthenticationError):
    """Raised when token has expired."""

    def __init__(self):
        super().__init__("Token has expired")


class InvalidTokenError(AuthenticationError):
    """Raised when token is invalid."""

    def __init__(self):
        super().__init__("Invalid token")


class UserNotFoundError(AuthenticationError):
    """Raised when user is not found."""

    def __init__(self):
        super().__init__("User not found")


class UserExistsError(AuthenticationError):
    """Raised when user already exists."""

    def __init__(self, email: str):
        super().__init__(f"User with email {email} already exists")
        self.email = email


class UserInactiveError(AuthenticationError):
    """Raised when user is inactive."""

    def __init__(self):
        super().__init__("User account is inactive")


# ============================================================================
# Password Utilities
# ============================================================================


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================================
# JWT Utilities
# ============================================================================


def create_access_token(
    user_id: UUID,
    expires_delta: Optional[timedelta] = None,
) -> Token:
    """
    Create a JWT access token for a user.
    
    Args:
        user_id: The user's ID to encode in the token.
        expires_delta: Optional expiration time delta. If not provided,
            uses the configured default.
            
    Returns:
        Token object with access_token, token_type, and expires_in.
    """
    settings = get_settings()

    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
    }

    access_token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=int(expires_delta.total_seconds()),
    )


def decode_access_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT access token.
    
    Args:
        token: The JWT token to decode.
        
    Returns:
        TokenPayload with user ID and timestamps.
        
    Raises:
        TokenExpiredError: If the token has expired.
        InvalidTokenError: If the token is invalid.
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenPayload(
            sub=payload["sub"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
        )
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError()
    except JWTError:
        raise InvalidTokenError()


# ============================================================================
# Authentication Service
# ============================================================================


class AuthService:
    """
    Authentication service for user management.
    
    Provides methods for:
    - User registration
    - User login
    - Token validation
    - User lookup
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def register_user(self, email: str, password: str) -> User:
        """
        Register a new user.
        
        Args:
            email: User's email address.
            password: User's password (will be hashed).
            
        Returns:
            The created User object.
            
        Raises:
            UserExistsError: If a user with this email already exists.
        """
        # Check if user exists
        existing = await self._get_user_by_email(email)
        if existing:
            raise UserExistsError(email)

        # Create user
        user = User(
            email=email,
            hashed_password=hash_password(password),
            is_active=True,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def authenticate_user(self, email: str, password: str) -> User:
        """
        Authenticate a user with email and password.
        
        Args:
            email: User's email address.
            password: User's password.
            
        Returns:
            The authenticated User object.
            
        Raises:
            InvalidCredentialsError: If credentials are invalid.
            UserInactiveError: If user is inactive.
        """
        user = await self._get_user_by_email(email)
        if not user:
            raise InvalidCredentialsError()

        if not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()

        if not user.is_active:
            raise UserInactiveError()

        return user

    async def login(self, email: str, password: str) -> tuple[User, Token]:
        """
        Login a user and return access token.
        
        Args:
            email: User's email address.
            password: User's password.
            
        Returns:
            Tuple of (User, Token).
            
        Raises:
            InvalidCredentialsError: If credentials are invalid.
            UserInactiveError: If user is inactive.
        """
        user = await self.authenticate_user(email, password)
        token = create_access_token(user.id)
        return user, token

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """
        Get a user by ID.
        
        Args:
            user_id: The user's UUID.
            
        Returns:
            User object or None if not found.
        """
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_current_user(self, token: str) -> User:
        """
        Get the current user from an access token.
        
        Args:
            token: JWT access token.
            
        Returns:
            The authenticated User object.
            
        Raises:
            InvalidTokenError: If token is invalid.
            TokenExpiredError: If token has expired.
            UserNotFoundError: If user does not exist.
            UserInactiveError: If user is inactive.
        """
        payload = decode_access_token(token)
        user_id = UUID(payload.sub)

        user = await self.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundError()

        if not user.is_active:
            raise UserInactiveError()

        return user

    async def _get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email address."""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
