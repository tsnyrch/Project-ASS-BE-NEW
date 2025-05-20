from datetime import datetime, timezone

from sqlalchemy import select, func

from app.models.measurement import MeasurementConfigOrm, MeasurementConfigSchema
from app.utils.db_session import get_db_session


class SettingsRepository:
    """
    Repository for application settings operations
    """

    async def _get_config_count(self) -> int:
        """
        Get count of config records in the database
        """
        async with get_db_session() as session:
            count = await session.execute(
                select(func.count()).select_from(MeasurementConfigOrm)
            )
            return count.scalar_one()

    async def _create_default_measurement_config(self) -> MeasurementConfigSchema:
        """
        Create a default measurement config in the database and return as schema
        """
        async with get_db_session() as session:
            default_config = MeasurementConfigOrm(
                measurement_frequency=60,  # 60 minutes default
                first_measurement=datetime(2023, 4, 26, 8, 0, 0, tzinfo=timezone.utc),
                rgb_camera=True,
                multispectral_camera=False,
                number_of_sensors=1,
                length_of_ae=10,  # 10 minutes default
            )
            session.add(default_config)
            # Commit happens automatically when context manager exits
            await session.flush()  # Ensure the object has an ID
            await session.refresh(default_config)
            return MeasurementConfigSchema.from_orm(default_config)

    async def get_measurement_config(self) -> MeasurementConfigSchema:
        """
        Get the current measurement configuration
        """
        async with get_db_session() as session:
            config_count = await self._get_config_count()
            if config_count == 0:
                # Create and return default config as schema
                return await self._create_default_measurement_config()
            else:
                result = await session.execute(
                    select(MeasurementConfigOrm)
                    .order_by(MeasurementConfigOrm.id.desc())
                    .limit(1)
                )
                config = result.scalars().first()
                return MeasurementConfigSchema.from_orm(config)

    async def update_measurement_config(
        self, config: MeasurementConfigSchema
    ) -> MeasurementConfigSchema:
        """
        Update the measurement configuration
        """
        async with get_db_session() as session:
            # Check if a config already exists
            config_count = await self._get_config_count()
        
            if config_count == 0:
                # Create new config if none exists
                new_config = MeasurementConfigOrm(
                    measurement_frequency=config.measurement_frequency,
                    first_measurement=config.first_measurement,
                    rgb_camera=config.rgb_camera,
                    multispectral_camera=config.multispectral_camera,
                    number_of_sensors=config.number_of_sensors,
                    length_of_ae=config.length_of_ae,
                )
                session.add(new_config)
                await session.flush()  # Ensure the object has an ID
                await session.refresh(new_config)
                return MeasurementConfigSchema.from_orm(new_config)
            else:
                # Update existing config
                result = await session.execute(
                    select(MeasurementConfigOrm)
                    .order_by(MeasurementConfigOrm.id.desc())
                    .limit(1)
                )
                existing_config = result.scalars().first()
            
                # Update fields
                existing_config.measurement_frequency = config.measurement_frequency
                existing_config.first_measurement = config.first_measurement
                existing_config.rgb_camera = config.rgb_camera
                existing_config.multispectral_camera = config.multispectral_camera
                existing_config.number_of_sensors = config.number_of_sensors
                existing_config.length_of_ae = config.length_of_ae
            
                await session.flush()
                await session.refresh(existing_config)
                return MeasurementConfigSchema.from_orm(existing_config)
