from datetime import datetime
from fastapi import status, APIRouter, Depends
from fastapi.responses import JSONResponse
from fastapi_restful.cbv import cbv
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.services.cron_scheduler import CronScheduler
from app.services.measurement_service import MeasurementService
from app.services.settings_service import SettingsService
from app.models.measurement import MeasurementInfoSchema
from app.controllers.user_controller import get_current_user
from app.models.user import TokenPayloadSchema

system_router = APIRouter(
    tags=["system"],
    responses={404: {"description": "Not found"}}
)

class HealthCheckResponse(BaseModel):
    status: str
    service: str
    code: int

class WelcomeResponse(BaseModel):
    message: str

class SchedulerStatusResponse(BaseModel):
    active: bool
    next_scheduled_time: Optional[datetime] = None
    interval_minutes: Optional[int] = None
    config_id: Optional[int] = None
    
class ManualTriggerResponse(BaseModel):
    success: bool
    message: str
    measurement: Optional[MeasurementInfoSchema] = None

@cbv(system_router)
class SystemController:

    @system_router.get(
        "/", 
        include_in_schema=False,
        response_model=WelcomeResponse
    )
    async def root(self) -> WelcomeResponse:
        """Display welcome message."""
        return WelcomeResponse(message="Hello World!")

    @system_router.get(
        "/health", 
        include_in_schema=False,
        response_model=HealthCheckResponse
    )
    async def healthcheck(self) -> JSONResponse:
        """Health check endpoint for monitoring and load balancers."""
        data = HealthCheckResponse(
            status="ok",
            service="fast-api-docker-poetry",
            code=status.HTTP_200_OK
        )
        return JSONResponse(data.dict(), status_code=status.HTTP_200_OK)
        
    @system_router.get(
        "/scheduler/status", 
        response_model=SchedulerStatusResponse,
        summary="Get measurement scheduler status",
        description="Returns information about the current state of the measurement scheduler"
    )
    async def get_scheduler_status(self) -> SchedulerStatusResponse:
        """Get the current status of the measurement scheduler."""
        scheduler = CronScheduler.get_instance()
        
        return SchedulerStatusResponse(
            active=scheduler.task is not None and not scheduler.task.done(),
            next_scheduled_time=scheduler.next_scheduled_date,
            interval_minutes=scheduler.minutes_interval,
            config_id=scheduler.config_id
        )
        
    @system_router.post(
        "/scheduler/trigger",
        response_model=ManualTriggerResponse,
        summary="Manually trigger a scheduled measurement",
        description="Manually triggers a measurement using the current configuration"
    )
    async def trigger_scheduled_measurement(
        self,
        current_user: TokenPayloadSchema = Depends(get_current_user)
    ) -> ManualTriggerResponse:
        """Manually trigger a scheduled measurement using current configuration."""
        try:
            # Get measurement service and settings service
            measurement_service = MeasurementService()
            settings_service = SettingsService()
            
            # Get current measurement configuration
            config = await settings_service.get_measurement_config()
            
            # Start a measurement with the current configuration
            measurement = await measurement_service.start_measurement_by_config(config)
            
            if measurement:
                return ManualTriggerResponse(
                    success=True,
                    message=f"Measurement triggered successfully with ID: {measurement.id}",
                    measurement=measurement
                )
            else:
                return ManualTriggerResponse(
                    success=False,
                    message="Failed to trigger measurement"
                )
                
        except Exception as e:
            return ManualTriggerResponse(
                success=False,
                message=f"Error triggering measurement: {str(e)}"
            )
