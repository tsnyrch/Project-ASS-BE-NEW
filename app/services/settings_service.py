from datetime import datetime, timezone

from app.models.measurement import MeasurementConfigSchema
from app.repository.settings_repository import SettingsRepository
from app.services.cron_scheduler import CronScheduler


class SettingsService:
    """
    Service for application settings operations
    """
    def __init__(self):
        self.settings_repo = SettingsRepository()

    async def get_measurement_config(self) -> MeasurementConfigSchema:
        """
        Get the current measurement configuration
        """
        return await self.settings_repo.get_measurement_config()

    async def update_measurement_config(self, config: MeasurementConfigSchema) -> MeasurementConfigSchema:
        """
        Update the measurement configuration

        This method also updates the measurement scheduler if frequency or first measurement time changes
        """
        old_config = await self.settings_repo.get_measurement_config()

        # Ensure both datetimes are timezone-aware
        if config.first_measurement.tzinfo is None:
            config.first_measurement = config.first_measurement.replace(tzinfo=timezone.utc)

        if old_config.first_measurement.tzinfo is None:
            old_config.first_measurement = old_config.first_measurement.replace(tzinfo=timezone.utc)

        # Update scheduler if frequency or first measurement changed
        if (
                config.measurement_frequency != old_config.measurement_frequency or
                config.first_measurement != old_config.first_measurement
        ):
            scheduler = CronScheduler.get_instance()
            scheduler.set_new_schedule(
                config.measurement_frequency,
                config.first_measurement
            )

        # Update config in repository
        return await self.settings_repo.update_measurement_config(config)
