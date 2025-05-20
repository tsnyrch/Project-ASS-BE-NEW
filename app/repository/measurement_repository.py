from datetime import datetime
from typing import List, Tuple, Optional

from sqlalchemy import select, between, desc

from app.models.measurement import MeasurementInfoOrm, MeasurementInfoSchema
from app.models.pageable import PageRequestSchema
from app.repository.base_repository import BaseRepository
from app.utils.db_session import get_db_session


class MeasurementRepository(BaseRepository):
    """
    Repository for measurement operations
    """

    def __init__(self):
        super().__init__(MeasurementInfoOrm)

    async def get_latest_measurement_info(self) -> List[MeasurementInfoOrm]:
        """
        Get the latest measurements
        """
        async with get_db_session() as session:
            # Query for the latest 5 measurements ordered by date_time
            result = await session.execute(
                select(MeasurementInfoOrm)
                .order_by(desc(MeasurementInfoOrm.date_time))
                .limit(5)
            )
            return result.scalars().all()

    async def get_measurement_history(
        self, start_date: datetime, end_date: datetime
    ) -> List[MeasurementInfoOrm]:
        """
        Get measurement history within a date range
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(MeasurementInfoOrm)
                .where(between(MeasurementInfoOrm.date_time, start_date, end_date))
                .order_by(desc(MeasurementInfoOrm.date_time))
            )
            return result.scalars().all()

    async def get_measurement_by_id(
        self, measurement_id: int
    ) -> Optional[MeasurementInfoOrm]:
        """
        Get a measurement by ID
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(MeasurementInfoOrm).where(
                    MeasurementInfoOrm.id == measurement_id
                )
            )
            return result.scalars().first()

    async def save_new_measurement(
        self, measurement: MeasurementInfoOrm
    ) -> "MeasurementInfoSchema":
        """
        Save a new measurement and return as schema
        """
        async with get_db_session() as session:
            session.add(measurement)
            # Commit happens automatically when context manager exits
            await session.flush()  # Ensure the object has an ID
            await session.refresh(measurement)
            return MeasurementInfoSchema.from_orm(measurement)

    async def delete_measurement(self, measurement: MeasurementInfoOrm) -> None:
        """
        Delete a measurement
        """
        await self.delete(measurement)

    async def get_paged_measurements(
        self, pageable: PageRequestSchema
    ) -> Tuple[List[MeasurementInfoOrm], int]:
        """
        Get paginated measurements
        """
        return await self.get_paged_items(pageable, {})
