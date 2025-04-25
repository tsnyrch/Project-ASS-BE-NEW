from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, FileResponse
from fastapi_restful.cbv import cbv
import logging
from pydantic import BaseModel

from app.middleware.auth import get_current_user
from app.models.measurement import MeasurementInfoOrm, MeasurementInfoSchema, MeasurementLatestSchema, MeasurementHistorySchema
from app.models.user import TokenPayloadSchema
from app.services.measurement_service import MeasurementService
from app.services.settings_service import SettingsService
from app.services.cron_scheduler import CronScheduler

# Set up logging
logger = logging.getLogger(__name__)

# Create router
measurement_router = APIRouter()

class MeasurementStartResponse(BaseModel):
    success: bool
    message: str
    measurement: Optional[MeasurementInfoSchema] = None

@cbv(measurement_router)
class MeasurementController:
    """
    Controller for measurement-related endpoints
    """
    def __init__(self):
        self.measurement_service = MeasurementService()
        self.settings_service = SettingsService()
        self.scheduler = CronScheduler.get_instance()
        
        # Register the measurement job with the scheduler
        self.scheduler.register_job(self.start_measurement_logic)

    @measurement_router.get(
        "/measurements/latest", 
        response_model=MeasurementLatestSchema, 
        summary="Get latest measurements",
        description="Retrieves the most recent measurement data along with information about the next scheduled measurement"
    )
    async def get_latest_measurement(
        self, current_user: TokenPayloadSchema = Depends(get_current_user)
    ) -> MeasurementLatestSchema:
        """
        Get the latest measurement data and information about next scheduled measurement.
        
        Returns:
            - Last backup timestamp
            - Last measurement timestamp
            - Next planned measurement timestamp
            - Latest measurement data
        """
        latest_measurements = await self.measurement_service.get_latest_measurement_info() or []
        planned_measurement = self.scheduler.next_scheduled_date
        
        latest_measurements_schema = [
            MeasurementInfoSchema.from_orm(m) for m in latest_measurements
        ]
        
        last_measurement_date = latest_measurements_schema[0].date_time if latest_measurements_schema else None
        
        return MeasurementLatestSchema(
            last_backup=datetime.now(),  # Placeholder, replace with actual backup information
            last_measurement=last_measurement_date,
            planned_measurement=planned_measurement,
            latest_measurement=latest_measurements_schema
        )

    @measurement_router.get(
        "/measurements/history", 
        response_model=MeasurementHistorySchema, 
        summary="Get measurement history",
        description="Retrieves the measurement history within a specified date range"
    )
    async def get_measurement_history(
        self,
        start_date: datetime = Query(..., description="Start date for history range (ISO format)"),
        end_date: datetime = Query(..., description="End date for history range (ISO format)"),
        current_user: TokenPayloadSchema = Depends(get_current_user)
    ) -> MeasurementHistorySchema:
        """
        Get measurement history within a date range.
        
        Allows filtering measurements by start and end dates to analyze historical data.
        
        Parameters:
            - start_date: The beginning of the date range (ISO format)
            - end_date: The end of the date range (ISO format)
        """
        measurements_history = await self.measurement_service.get_measurement_history(start_date, end_date)
        measurements_schema = [MeasurementInfoSchema.from_orm(m) for m in measurements_history]
        
        return MeasurementHistorySchema(measurements=measurements_schema)

    @measurement_router.get(
        "/measurements/{measurement_id}",
        summary="Get a specific measurement",
        description="Retrieves data for a specific measurement by its ID",
        response_model=MeasurementInfoSchema
    )
    async def get_measurement_by_id(
        self, measurement_id: int, current_user: TokenPayloadSchema = Depends(get_current_user)
    ) -> MeasurementInfoSchema:
        """
        Get a specific measurement by ID.
        
        Retrieves detailed information about a specific measurement identified by its unique ID.
        In a real implementation, this would return the measurement data files.
        
        Parameters:
            - measurement_id: The unique identifier for the measurement
        """
        measurement = await self.measurement_service.get_measurement(measurement_id)
        if not measurement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Measurement not found"
            )
            
        # This is a placeholder for the actual file generation and download
        # In a real implementation, you would generate or retrieve the measurement data files
        # and return them as a downloadable archive
        
        return MeasurementInfoSchema.from_orm(measurement)

    @measurement_router.post(
        "/measurements/start", 
        response_model=MeasurementStartResponse, 
        summary="Start a new measurement",
        description="Manually initiates a new measurement process"
    )
    async def start_measurement(
        self, current_user: TokenPayloadSchema = Depends(get_current_user)
    ) -> MeasurementStartResponse:
        """
        Start a new measurement manually.
        
        Triggers an immediate measurement using the current configuration settings.
        This endpoint is useful for on-demand measurements outside the regular schedule.
        """
        try:
            measurement = await self.start_measurement_logic(scheduled=False)
            return MeasurementStartResponse(
                success=True,
                message="Measurement started successfully",
                measurement=measurement
            )
        except Exception as e:
            return MeasurementStartResponse(
                success=False,
                message=f"Failed to start measurement: {str(e)}"
            )

    async def start_measurement_logic(self, scheduled: bool = False) -> MeasurementInfoSchema:
        """
        Logic for starting a new measurement
        
        Can be called manually or by the scheduler
        """
        logger.info(f"Starting measurement (scheduled: {scheduled})")

        try:
            # Get current configuration
            config = await self.settings_service.get_measurement_config()
            
            # Create new measurement record
            new_measurement = MeasurementInfoOrm(
                date_time=datetime.now(),
                rgb_camera=config.rgb_camera,
                multispectral_camera=config.multispectral_camera,
                number_of_sensors=config.number_of_sensors,
                length_of_ae=config.length_of_ae,
                scheduled=scheduled
            )
            
            saved_measurement = await self.measurement_service.create_measurement(new_measurement)
            logger.info(f"Created measurement with ID: {saved_measurement.id}")
            
            # Start camera measurements if enabled
            if config.rgb_camera:
                await self.measurement_service.start_rgb_measurement(
                    saved_measurement.id, saved_measurement.date_time, config.length_of_ae
                )
                
            if config.multispectral_camera:
                await self.measurement_service.start_multispectral_measurement(
                    saved_measurement.id, saved_measurement.date_time
                )
                
            return MeasurementInfoSchema.from_orm(saved_measurement)
            
        except Exception as e:
            logger.error(f"Error in measurement logic: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start measurement: {str(e)}"
            )