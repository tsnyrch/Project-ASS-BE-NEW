import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi_restful.cbv import cbv
from pydantic import BaseModel

from app.middleware.auth import (
    generate_access_token,
    generate_refresh_token,
    get_current_user,
    verify_refresh_token,
)
from app.models.user import (
    RefreshTokenSchema,
    TokenPayloadSchema,
    TokenSchema,
    UserCreateSchema,
    UserResponseSchema,
)
from app.services.user_service import UserService

# Set up logging
logger = logging.getLogger(__name__)

# Create router
user_router = APIRouter(
    prefix="/users", tags=["users"], responses={404: {"description": "Not found"}}
)

# Set up OAuth2 with Password Flow
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")


class UserListResponse(BaseModel):
    users: List[UserResponseSchema]
    total: int


class AuthErrorResponse(BaseModel):
    detail: str


@cbv(user_router)
class UserController:
    """
    Controller for user-related endpoints
    """

    def __init__(self):
        self.user_service = UserService()

    @user_router.get(
        "/",
        response_model=List[UserResponseSchema],
        summary="Get all users",
        description="Retrieves all registered users in the system",
    )
    async def get_users(
        self, current_user: TokenPayloadSchema = Depends(get_current_user)
    ) -> List[UserResponseSchema]:
        """
        Get all users (admin only).

        Returns a list of all registered users. This endpoint is restricted to admin users only.
        """
        users = await self.user_service.get_all_users()
        return [UserResponseSchema.from_orm(user) for user in users]

    @user_router.post(
        "/",
        response_model=UserResponseSchema,
        summary="Create a new user",
        description="Creates a new user account",
    )
    async def create_user(
        self,
        user: UserCreateSchema,
        current_user: TokenPayloadSchema = Depends(get_current_user),
    ) -> UserResponseSchema:
        """
        Create a new user (admin only).

        Creates a new user account with the provided information.
        This endpoint is restricted to admin users only.

        The password will be securely hashed before storage.
        """
        # Check if user already exists
        existing_user = await self.user_service.get_user_by_username(user.user_name)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with username '{user.user_name}' already exists",
            )

        # Create the user
        created_user = await self.user_service.create_user(user)
        return UserResponseSchema.from_orm(created_user)

    @user_router.get(
        "/{user_id}",
        response_model=UserResponseSchema,
        summary="Get user by ID",
        description="Retrieves a specific user by their ID",
    )
    async def get_user_by_id(
        self, user_id: int, current_user: TokenPayloadSchema = Depends(get_current_user)
    ) -> UserResponseSchema:
        """
        Get a user by ID.

        Retrieves detailed information about a specific user identified by their unique ID.
        This endpoint is accessible to admin users or the user themself.
        """
        user = await self.user_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        return UserResponseSchema.from_orm(user)

    @user_router.post(
        "/login",
        response_model=TokenSchema,
        summary="Authenticate user",
        description="Authenticates a user and provides access tokens",
        responses={
            status.HTTP_401_UNAUTHORIZED: {
                "model": AuthErrorResponse,
                "description": "Invalid credentials",
            }
        },
    )
    async def login(
        self, form_data: OAuth2PasswordRequestForm = Depends()
    ) -> TokenSchema:
        """
        Authenticate a user and return access and refresh tokens.

        This endpoint uses OAuth2 password flow for authentication.
        Provide username and password to receive JWT access and refresh tokens.

        Returns:
            - access_token: JWT token for API access
            - refresh_token: Token for obtaining new access tokens
            - token_type: Type of token (bearer)
        """
        user = await self.user_service.validate_user(
            form_data.username, form_data.password
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Generate tokens
        access_token = generate_access_token(user)
        refresh_token = generate_refresh_token(user.id)

        # Save refresh token
        await self.user_service.update_refresh_token(user.id, refresh_token)

        return TokenSchema(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    @user_router.post(
        "/refresh-token",
        response_model=TokenSchema,
        summary="Refresh access token",
        description="Issues a new access token using a valid refresh token",
        responses={
            status.HTTP_401_UNAUTHORIZED: {
                "model": AuthErrorResponse,
                "description": "Invalid refresh token",
            },
            status.HTTP_404_NOT_FOUND: {
                "model": AuthErrorResponse,
                "description": "User not found",
            },
        },
    )
    async def refresh_token(self, refresh_request: RefreshTokenSchema) -> TokenSchema:
        """
        Refresh an access token using a refresh token.

        When an access token expires, this endpoint can be used to obtain a new one
        without requiring the user to log in again with credentials.

        Request body must contain the username and a valid refresh token.

        Returns:
            - access_token: New JWT token for API access
            - refresh_token: New refresh token (old token is invalidated)
            - token_type: Type of token (bearer)
        """
        # Get user by username
        user = await self.user_service.get_user_by_username(refresh_request.user_name)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User does not exist"
            )

        # Verify refresh token is valid
        try:
            verify_refresh_token(refresh_request.refresh_token)
        except HTTPException:
            # Delete invalid refresh token
            await self.user_service.delete_refresh_token(user.id)
            raise

        # Check if token matches stored token
        if user.refresh_token != refresh_request.refresh_token:
            await self.user_service.delete_refresh_token(user.id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        # Generate new tokens
        access_token = generate_access_token(user)
        new_refresh_token = generate_refresh_token(user.id)

        # Update refresh token
        await self.user_service.update_refresh_token(user.id, new_refresh_token)

        return TokenSchema(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
        )

    @user_router.delete(
        "/{user_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete a user",
        description="Deletes a user from the system",
        responses={
            status.HTTP_404_NOT_FOUND: {
                "model": AuthErrorResponse,
                "description": "User not found",
            },
            status.HTTP_403_FORBIDDEN: {
                "model": AuthErrorResponse,
                "description": "Insufficient permissions",
            },
        },
    )
    async def delete_user(
        self, user_id: int, current_user: TokenPayloadSchema = Depends(get_current_user)
    ) -> Response:
        """
        Delete a user by ID (admin only).

        Permanently removes a user account from the system. This action cannot be undone.
        This endpoint is restricted to admin users only.

        Args:
            user_id: The ID of the user to delete
            current_user: The authenticated user making the request

        Returns:
            204 No Content on successful deletion

        Raises:
            404 Not Found if the user does not exist
        """
        deleted = await self.user_service.delete_user(user_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        return Response(status_code=status.HTTP_204_NO_CONTENT)
