from typing import List, Optional, Dict, Any, Union
from sqlalchemy import func, or_, desc, asc, select
from ..models.camera_file import CameraFile
from .base_repository import BaseRepository
from app.utils.db_session import get_db_session


class CameraFileRepository(BaseRepository):
    """Repository for managing camera file records in the database."""
    
    def __init__(self):
        super().__init__(CameraFile)
    
    async def create_camera_file(self, file_data: Dict[str, Any]) -> CameraFile:
        """
        Create a new camera file record.
        
        Args:
            file_data: Dictionary containing camera file data
            
        Returns:
            Created CameraFile instance
        """
        async with get_db_session() as session:
            camera_file = CameraFile(**file_data)
            session.add(camera_file)
            await session.flush()  # Ensure the object has an ID
            await session.refresh(camera_file)
            return camera_file
    
    async def create_multispectral_set(self, parent_data: Dict[str, Any], children_data: List[Dict[str, Any]]) -> CameraFile:
        """
        Create a multispectral image set with parent and child images.
        
        Args:
            parent_data: Dictionary containing parent file data
            children_data: List of dictionaries containing child file data
            
        Returns:
            Parent CameraFile instance
        """
        async with get_db_session() as session:
            # Create parent record
            parent = CameraFile(**parent_data)
            session.add(parent)
            await session.flush()  # Flush to get parent ID without committing
            
            # Create children records with parent ID
            for child_data in children_data:
                child_data["parent_id"] = parent.id
                child = CameraFile(**child_data)
                session.add(child)
            
            # Commit happens automatically when context manager exits
            await session.refresh(parent)
            return parent
    
    async def get_by_id(self, file_id: str) -> Optional[CameraFile]:
        """
        Get a camera file record by ID.
        
        Args:
            file_id: ID of the camera file
            
        Returns:
            CameraFile instance if found, None otherwise
        """
        async with get_db_session() as session:
            result = await session.execute(select(CameraFile).filter(CameraFile.id == file_id))
            return result.scalars().first()
    
    async def get_by_camera_id(self, camera_id: str, skip: int = 0, limit: int = 100) -> List[CameraFile]:
        """
        Get camera file records by camera ID.
        
        Args:
            camera_id: Camera ID
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            
        Returns:
            List of CameraFile instances
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(CameraFile)
                .filter(CameraFile.camera_id == camera_id)
                .order_by(desc(CameraFile.created_at))
                .offset(skip)
                .limit(limit)
            )
            return result.scalars().all()
    
    async def get_multispectral_set(self, parent_id: str) -> Dict[str, Any]:
        """
        Get a multispectral image set by parent ID.
        
        Args:
            parent_id: ID of the parent file
            
        Returns:
            Dictionary containing parent and children files
        """
        async with get_db_session() as session:
            parent = await self.get_by_id(parent_id)
            if not parent:
                return None
                
            result = await session.execute(
                select(CameraFile)
                .filter(CameraFile.parent_id == parent_id)
                .order_by(asc(CameraFile.wavelength))
            )
            children = result.scalars().all()
            
            return {
                "parent": parent,
                "children": children
            }
    
    async def search_files(
        self, 
        search_term: Optional[str] = None,
        camera_id: Optional[str] = None,
        file_type: Optional[str] = None,
        is_uploaded: Optional[bool] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        skip: int = 0, 
        limit: int = 100,
        sort_by: str = "created_at",
        sort_desc: bool = True
    ) -> Dict[str, Any]:
        """
        Search for camera files with various filters.
        
        Args:
            search_term: Optional text to search in file name
            camera_id: Optional camera ID filter
            file_type: Optional file type filter (mime_type)
            is_uploaded: Optional filter for upload status
            start_date: Optional filter for created_at (format: 'YYYY-MM-DD')
            end_date: Optional filter for created_at (format: 'YYYY-MM-DD')
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            sort_by: Field to sort by
            sort_desc: Whether to sort in descending order
            
        Returns:
            Dictionary with items and total count
        """
        async with get_db_session() as session:
            # Build the base query
            query = select(CameraFile)
            
            # Apply filters
            conditions = []
            if search_term:
                conditions.append(CameraFile.file_name.ilike(f"%{search_term}%"))
                
            if camera_id:
                conditions.append(CameraFile.camera_id == camera_id)
                
            if file_type:
                conditions.append(CameraFile.mime_type == file_type)
                
            if is_uploaded is not None:
                conditions.append(CameraFile.is_uploaded == is_uploaded)
                
            if start_date:
                conditions.append(CameraFile.created_at >= start_date)
                
            if end_date:
                conditions.append(CameraFile.created_at <= end_date)
            
            # Only include parent files or files without a parent
            conditions.append(CameraFile.parent_id == None)
            
            # Apply all conditions to the query
            for condition in conditions:
                query = query.where(condition)
            
            # Get total count for pagination
            count_query = select(func.count()).select_from(CameraFile)
            for condition in conditions:
                count_query = count_query.where(condition)
                
            count_result = await session.execute(count_query)
            total = count_result.scalar()
            
            # Apply sorting
            sort_column = getattr(CameraFile, sort_by, CameraFile.created_at)
            if sort_desc:
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))
            
            # Apply pagination
            query = query.offset(skip).limit(limit)
            
            # Execute the query
            result = await session.execute(query)
            items = result.scalars().all()
            
            return {
                "items": items,
                "total": total
            }
    
    async def update_upload_status(self, file_id: str, is_uploaded: bool, cloud_url: Optional[str] = None) -> Optional[CameraFile]:
        """
        Update the upload status and cloud URL of a camera file.
        
        Args:
            file_id: ID of the camera file
            is_uploaded: New upload status
            cloud_url: Optional cloud URL
            
        Returns:
            Updated CameraFile instance or None if not found
        """
        async with get_db_session() as session:
            camera_file = await self.get_by_id(file_id)
            if not camera_file:
                return None
                
            camera_file.is_uploaded = is_uploaded
            if cloud_url:
                camera_file.cloud_url = cloud_url
                
            session.add(camera_file)
            await session.refresh(camera_file)
            return camera_file
    
    async def delete_file(self, file_id: str) -> bool:
        """
        Delete a camera file record.
        
        Args:
            file_id: ID of the camera file
            
        Returns:
            True if deleted, False otherwise
        """
        async with get_db_session() as session:
            camera_file = await self.get_by_id(file_id)
            if not camera_file:
                return False
                
            await session.delete(camera_file)
            return True
    
    async def delete_multispectral_set(self, parent_id: str) -> bool:
        """
        Delete a multispectral image set.
        
        Args:
            parent_id: ID of the parent file
            
        Returns:
            True if deleted, False otherwise
        """
        # Due to cascade delete setup, deleting the parent will also delete children
        return await self.delete_file(parent_id)