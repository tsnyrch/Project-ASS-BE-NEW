import os
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import Depends, HTTPException
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
    OAuth2PasswordBearer,
)
from jose import JWTError, jwt
from starlette import status

from app.models.user import TokenPayloadSchema, UserOrm

# Using environment variables with defaults for JWT secrets
ACCESS_TOKEN_SECRET = os.getenv(
    "ACCESS_TOKEN_SECRET", "access_secret_key_for_development"
)
REFRESH_TOKEN_SECRET = os.getenv(
    "REFRESH_TOKEN_SECRET", "refresh_secret_key_for_development"
)

# Set up Bearer token scheme
security = HTTPBearer()

# OAuth2 scheme for Swagger UI integration
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")


async def get_token_from_authorization(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    return credentials.credentials


async def get_current_user(
    token: str = Depends(get_token_from_authorization),
) -> TokenPayloadSchema:
    """
    Validate JWT token and extract user information
    """
    try:
        payload = jwt.decode(token, ACCESS_TOKEN_SECRET, algorithms=["HS256"])
        return TokenPayloadSchema(**payload)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def generate_access_token(user: UserOrm) -> str:
    """
    Generate a short-lived access token for the authenticated user
    """
    if not user or not user.id:
        raise ValueError("Invalid user data for token generation")

    payload = {
        "id": user.id,
        "is_admin": user.is_admin,
        "user_name": user.user_name,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "exp": datetime.utcnow() + timedelta(minutes=30),  # 30 minutes expiration
    }

    return jwt.encode(payload, ACCESS_TOKEN_SECRET, algorithm="HS256")


def generate_refresh_token(user_id: int) -> str:
    """
    Generate a long-lived refresh token for token renewal
    """
    if not user_id:
        raise ValueError("Invalid user ID for refresh token generation")

    payload = {
        "id": user_id,
        "exp": datetime.utcnow() + timedelta(days=90),  # 90 days expiration
    }

    return jwt.encode(payload, REFRESH_TOKEN_SECRET, algorithm="HS256")


def verify_refresh_token(token: str) -> Dict[str, Any]:
    """
    Verify a refresh token and return its payload
    """
    try:
        payload = jwt.decode(token, REFRESH_TOKEN_SECRET, algorithms=["HS256"])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
