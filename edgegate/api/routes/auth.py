"""
Authentication API routes.

Provides:
- POST /auth/register - Register new user
- POST /auth/login - Login and get access token
- GET /auth/me - Get current user profile
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.db import get_session
from edgegate.services.auth import (
    AuthService,
    Token,
    UserResponse,
    InvalidCredentialsError,
    UserExistsError,
    UserInactiveError,
)
from edgegate.api.deps import CurrentUser


router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================================================
# Schemas
# ============================================================================


class RegisterRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    """Request body for user login."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response with access token."""

    access_token: str
    token_type: str
    expires_in: int


# ============================================================================
# Routes
# ============================================================================


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    """
    Register a new user account.
    
    - **email**: Valid email address (must be unique)
    - **password**: Password (min 8 characters recommended)
    
    Returns the created user profile.
    """
    auth_service = AuthService(session)

    try:
        user = await auth_service.register_user(
            email=request.email,
            password=request.password,
        )
        return UserResponse.model_validate(user)
    except UserExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get access token",
)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """
    Authenticate with email and password, receive JWT access token.
    
    - **email**: Registered email address
    - **password**: Account password
    
    Returns access token with expiration time.
    """
    auth_service = AuthService(session)

    try:
        user, token = await auth_service.login(
            email=request.email,
            password=request.password,
        )
        return TokenResponse(
            access_token=token.access_token,
            token_type=token.token_type,
            expires_in=token.expires_in,
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except UserInactiveError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message,
        )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(current_user: CurrentUser) -> UserResponse:
    """
    Get the profile of the currently authenticated user.
    
    Requires valid JWT token in Authorization header.
    """
    return UserResponse.model_validate(current_user)
