from typing import Optional

from passlib.context import CryptContext
from pydantic import BaseModel, validator
from sqlalchemy import Boolean, Column, String, Text

from app.models.base import BaseOrm, BaseSchema

# Set up password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserOrm(BaseOrm):
    """
    User model representing application users with authentication
    """

    __tablename__ = "users"

    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    user_name = Column(String(50), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    refresh_token = Column(Text, nullable=True)

    def validate_password(self, password: str) -> bool:
        """
        Validates a password against the user's stored hash
        """
        return pwd_context.verify(password, self.password)


class UserCreateSchema(BaseSchema):
    """
    Schema for creating a new user
    """

    __orm__ = UserOrm
    __transient_fields__ = ["id", "created_at", "updated_at"]

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    user_name: str
    password: str
    is_admin: bool = False

    @validator("user_name")
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        return v


class UserResponseSchema(BaseSchema):
    """
    Schema for user response data (excludes password)
    """

    __orm__ = UserOrm

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    user_name: str
    is_admin: bool = False


class UserLoginSchema(BaseSchema):
    """
    Schema for user login requests
    """

    user_name: str
    password: str


class TokenSchema(BaseModel):
    """
    Schema for authentication tokens
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayloadSchema(BaseSchema):
    """
    Schema for JWT token payload
    """

    id: int
    user_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class RefreshTokenSchema(BaseSchema):
    """
    Schema for refresh token requests
    """

    user_name: str
    refresh_token: str
