from typing import Optional, List

from app.models.user import UserOrm, UserCreateSchema
from app.repository.user_repository import UserRepository


class UserService:
    """
    Service for user management operations
    """

    def __init__(self):
        self.user_repo: UserRepository = UserRepository()

    async def get_all_users(self) -> List[UserOrm]:
        """
        Get all users
        """
        return await self.user_repo.get_all_users()

    async def get_user_by_id(self, user_id: int) -> Optional[UserOrm]:
        """
        Get a user by ID
        """
        return await self.user_repo.get_user_by_id(user_id)

    async def get_user_by_username(self, username: str) -> Optional[UserOrm]:
        """
        Get a user by username
        """
        return await self.user_repo.get_user_by_username(username)

    async def create_user(self, user_data: UserCreateSchema) -> UserOrm:
        """
        Create a new user
        """
        user_orm = user_data.to_orm()
        return await self.user_repo.create_user(user_orm)

    async def validate_user(self, username: str, password: str) -> Optional[UserOrm]:
        """
        Validate user credentials
        """
        user = await self.user_repo.get_user_by_username(username)
        if user and user.validate_password(password):
            return user
        return None

    async def update_refresh_token(self, user_id: int, refresh_token: str) -> None:
        """
        Update refresh token for a user
        """
        await self.user_repo.update_user_refresh_token(user_id, refresh_token)

    async def delete_refresh_token(self, user_id: int) -> None:
        """
        Delete refresh token for a user
        """
        await self.user_repo.delete_user_refresh_token(user_id)

    async def delete_user(self, user_id: int) -> bool:
        """
        Delete a user by ID

        Args:
            user_id: The ID of the user to delete

        Returns:
            bool: True if the user was successfully deleted, False if user not found
        """
        # Check if user exists
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        # Delete the user
        await self.user_repo.delete_by_id(user_id)
        return True
