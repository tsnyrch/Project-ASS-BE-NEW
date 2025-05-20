from typing import Optional
from sqlalchemy import select

from app.models.user import UserOrm, pwd_context
from app.repository.base_repository import BaseRepository
from app.utils.db_session import get_db_session


class UserRepository(BaseRepository):
    """
    Repository for user management operations
    """
    
    def __init__(self):
        super().__init__(UserOrm)

    async def get_all_users(self) -> list[UserOrm]:
        """
        Get all users from the database
        """
        async with get_db_session() as session:
            result = await session.execute(select(UserOrm))
            users = result.scalars().all()
            return users

    async def get_user_by_id(self, user_id: int) -> Optional[UserOrm]:
        """
        Get a user by ID
        """
        async with get_db_session() as session:
            result = await session.execute(select(UserOrm).where(UserOrm.id == user_id))
            user = result.scalars().first()
            return user

    async def get_user_by_username(self, username: str) -> Optional[UserOrm]:
        """
        Get a user by username
        """
        async with get_db_session() as session:
            result = await session.execute(select(UserOrm).where(UserOrm.user_name == username))
            user = result.scalars().first()
            return user

    async def create_user(self, user: UserOrm) -> UserOrm:
        """
        Create a new user with password hashing
        """
        # Hash the password before saving
        user.password = self._hash_password(user.password)
        return await self.save(user)

    async def update_user_refresh_token(self, user_id: int, refresh_token: Optional[str]) -> None:
        """
        Update or remove the refresh token for a user
        """
        async with get_db_session() as session:
            user = await session.get(UserOrm, user_id)
            if user:
                user.refresh_token = refresh_token
                # Commit happens automatically when context manager exits

    async def delete_user_refresh_token(self, user_id: int) -> None:
        """
        Remove the refresh token for a user
        """
        await self.update_user_refresh_token(user_id, None)

    @staticmethod
    def _hash_password(password: str) -> str:
        """
        Hash a password for secure storage
        """
        return pwd_context.hash(password)