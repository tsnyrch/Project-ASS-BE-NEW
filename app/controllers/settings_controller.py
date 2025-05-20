from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_restful.cbv import cbv
import logging
from pydantic import BaseModel

from app.middleware.auth import get_current_user
from app.models.measurement import MeasurementConfigSchema
from app.models.user import TokenPayloadSchema
from app.services.settings_service import SettingsService
from app.services.cron_scheduler import CronScheduler

# Set up logging
logger = logging.getLogger(__name__)

# Create router
settings_router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    responses={404: {"description": "Not found"}}
)

class ConfigUpdateResponse(BaseModel):
    success: bool
    message: str
    config: MeasurementConfigSchema

@cbv(settings_router)
class SettingsController:
    """
    Controller for application settings endpoints
    """
    def __init__(self):
        self.settings_service = SettingsService()

    @settings_router.get(
        "/measurement-config",
        response_model=MeasurementConfigSchema,
        summary="Get measurement configuration",
        description="Retrieves the current measurement configuration settings"
    )
    async def get_measurement_config(
        self, current_user: TokenPayloadSchema = Depends(get_current_user)
    ) -> MeasurementConfigSchema:
        """
        Get the current measurement configuration.

        Returns all settings related to the measurement process including frequencies,
        camera options, and sensor configurations.
        """
        return await self.settings_service.get_measurement_config()

    @settings_router.put(
        "/measurement-config",
        response_model=ConfigUpdateResponse,
        summary="Update measurement configuration",
        description="Updates the existing measurement configuration with new settings"
    )
    async def update_measurement_config(
        self,
        config: MeasurementConfigSchema,
        current_user: TokenPayloadSchema = Depends(get_current_user)
    ) -> ConfigUpdateResponse:
        """
        Update the measurement configuration.

        Modifies the existing configuration record with new values instead of creating a new one.
        Allows changing settings like measurement frequency, camera options, and sensor configurations.
        Performs validation to ensure the configuration is valid before applying changes.

        Requirements:
          - Measurement frequency must be greater than the length of AE
          - Currently the multispectral camera functionality is disabled
        """
        try:
            # Validate configuration
            if config.measurement_frequency <= config.length_of_ae:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Measurement frequency must be greater than length of AE"
                )

            # Update the existing configuration
            updated_config = await self.settings_service.update_measurement_config(config)

            # Reinitialize the scheduler with the new configuration
            scheduler = CronScheduler.get_instance()
            scheduler.set_new_schedule(
                updated_config.measurement_frequency,
                updated_config.first_measurement,
                updated_config.id
            )

            return ConfigUpdateResponse(
                success=True,
                message="Configuration updated successfully (existing record modified)",
                config=updated_config
            )

        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error updating measurement config: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update configuration: {str(e)}"
            )
