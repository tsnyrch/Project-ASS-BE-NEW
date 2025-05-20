from typing import List, Optional
from sqlalchemy import select

from app.models.measurement_file import MeasurementFileOrm
from app.repository.base_repository import BaseRepository
from app.utils.db_session import get_db_session

class MeasurementFileRepository(BaseRepository):
    """Repository for managing measurement files"""
    
    def __init__(self):
        super().__init__(MeasurementFileOrm)
    
    async def get_by_measurement_id(self, measurement_id: int) -> List[MeasurementFileOrm]:
        """
        Get all files for a specific measurement
        
        Args:
            measurement_id: ID of the measurement
            
        Returns:
            List of measurement files
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(MeasurementFileOrm).filter(MeasurementFileOrm.measurement_id == measurement_id)
            )
            return result.scalars().all()
    
    async def save_file(self, name: str, google_drive_file_id: str, measurement_id: int) -> MeasurementFileOrm:
        """
        Save a new file reference
        
        Args:
            name: Name of the file
            google_drive_file_id: ID of the file in Google Drive
            measurement_id: ID of the measurement
            
        Returns:
            Created measurement file record
        """
        file = MeasurementFileOrm(
            name=name, 
            google_drive_file_id=google_drive_file_id, 
            measurement_id=measurement_id
        )
        return await self.save(file)