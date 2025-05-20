import io
import logging
import zipfile
from datetime import datetime, timezone
from typing import Optional, Union, List

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi_restful.cbv import cbv
from pydantic import BaseModel

from app.middleware.auth import get_current_user
from app.models.measurement import (
    MeasurementConfigSchema,
    MeasurementConfigCreateSchema,
    MeasurementHistorySchema,
    MeasurementInfoOrm,
    MeasurementInfoSchema,
    MeasurementLatestSchema,
)
from app.models.measurement_file import MeasurementFileSchema
from app.models.user import TokenPayloadSchema
from app.services.cron_scheduler import CronScheduler
from app.services.google_drive_service import GoogleDriveService
from app.services.measurement_service import MeasurementService
from app.services.settings_service import SettingsService

# Set up logging
logger = logging.getLogger(__name__)

# Create router
measurement_router = APIRouter(
    prefix="/measurements",
    tags=["measurements"],
    responses={404: {"description": "Not found"}},
)


class MeasurementStartResponse(BaseModel):
    success: bool
    message: str
    measurement: Optional[MeasurementInfoSchema] = None


class FileUploadResponse(BaseModel):
    success: bool
    message: str
    file_id: Optional[str] = None


class FileDownloadRequest(BaseModel):
    file_id: str


@cbv(measurement_router)
class MeasurementController:
    """
    Controller for measurement-related endpoints
    """

    def __init__(self):
        self.measurement_service = MeasurementService()
        self.settings_service = SettingsService()
        self.scheduler = CronScheduler.get_instance()
        self.google_drive_service = GoogleDriveService()

        # Register the measurement job with the scheduler
        self.scheduler.register_job(self.start_measurement_logic)

    @measurement_router.get(
        "/latest",
        response_model=MeasurementLatestSchema,
        summary="Get latest measurements",
        description="Retrieves the most recent measurement data along with information about the next scheduled measurement",
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
        latest_measurements = (
            await self.measurement_service.get_latest_measurements_with_files() or []
        )
        planned_measurement = self.scheduler.next_scheduled_date

        # Convert to schema with files
        latest_measurements_schema = []
        for m in latest_measurements:
            schema = MeasurementInfoSchema.from_orm(m)
            if hasattr(m, 'files') and m.files:
                schema.files = []
                for file in m.files:
                    file_schema = MeasurementFileSchema.from_orm(file)
                    schema.files.append({
                        "id": file_schema.id,
                        "name": file_schema.name,
                        "google_drive_file_id": file_schema.google_drive_file_id,
                        "measurement_id": file_schema.measurement_id,
                        "created_at": file_schema.created_at,
                        "updated_at": file_schema.updated_at
                    })
            latest_measurements_schema.append(schema)

        last_measurement_date = (
            latest_measurements_schema[0].date_time
            if latest_measurements_schema
            else None
        )

        return MeasurementLatestSchema(
            last_backup=datetime.now(),  # Placeholder, replace with actual backup information
            last_measurement=last_measurement_date,
            planned_measurement=planned_measurement,
            latest_measurement=latest_measurements_schema,
        )

    @measurement_router.get(
        "/history",
        response_model=MeasurementHistorySchema,
        summary="Get measurement history",
        description="Retrieves the measurement history within a specified date range",
    )
    async def get_measurement_history(
        self,
        start_date: datetime = Query(
            ..., description="Start date for history range (ISO format)"
        ),
        end_date: datetime = Query(
            ..., description="End date for history range (ISO format)"
        ),
        current_user: TokenPayloadSchema = Depends(get_current_user),
    ) -> MeasurementHistorySchema:
        """
        Get measurement history within a date range.

        Allows filtering measurements by start and end dates to analyze historical data.

        Parameters:
            - start_date: The beginning of the date range (ISO format)
            - end_date: The end of the date range (ISO format)
        """
        measurements_history = await self.measurement_service.get_measurement_history_with_files(
            start_date, end_date
        )
        # Convert to schema with files
        measurements_schema = []
        for m in measurements_history:
            schema = MeasurementInfoSchema.from_orm(m)
            if hasattr(m, 'files') and m.files:
                schema.files = []
                for file in m.files:
                    file_schema = MeasurementFileSchema.from_orm(file)
                    schema.files.append({
                        "id": file_schema.id,
                        "name": file_schema.name,
                        "google_drive_file_id": file_schema.google_drive_file_id,
                        "measurement_id": file_schema.measurement_id,
                        "created_at": file_schema.created_at,
                        "updated_at": file_schema.updated_at
                    })
            measurements_schema.append(schema)

        return MeasurementHistorySchema(measurements=measurements_schema)

    @measurement_router.get(
        "/{measurement_id}",
        summary="Get a specific measurement",
        description="Retrieves data for a specific measurement by its ID",
        response_model=MeasurementInfoSchema,
    )
    async def get_measurement_by_id(
        self,
        measurement_id: int,
        current_user: TokenPayloadSchema = Depends(get_current_user),
    ) -> MeasurementInfoSchema:
        """
        Get a specific measurement by ID.

        Retrieves detailed information about a specific measurement identified by its unique ID.
        Includes a list of associated measurement files.

        Parameters:
            - measurement_id: The unique identifier for the measurement
        """
        measurement = await self.measurement_service.get_measurement_with_files(measurement_id)
        if not measurement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Measurement not found"
            )

        # Convert to schema with files
        schema = MeasurementInfoSchema.from_orm(measurement)
        if hasattr(measurement, 'files') and measurement.files:
            schema.files = []
            for file in measurement.files:
                file_schema = MeasurementFileSchema.from_orm(file)
                schema.files.append({
                    "id": file_schema.id,
                    "name": file_schema.name,
                    "google_drive_file_id": file_schema.google_drive_file_id,
                    "measurement_id": file_schema.measurement_id,
                    "created_at": file_schema.created_at,
                    "updated_at": file_schema.updated_at
                })
        return schema



    @measurement_router.get(
        "/{measurement_id}/download-all",
        summary="Download all files for measurement as ZIP",
        description="Downloads and packages all files for a measurement into a single ZIP archive",
    )
    async def download_all_measurement_files(
        self,
        measurement_id: int,
        current_user: TokenPayloadSchema = Depends(get_current_user),
    ):
        """
        Download all files for a measurement as a ZIP archive.

        This endpoint fetches all files associated with a measurement from Google Drive,
        packages them into a ZIP archive, and returns the archive as a response.

        Parameters:
            - measurement_id: ID of the measurement to download files for
        """
        try:
            logger.info(
                f"Starting download of all files for Measurement ID: {measurement_id}"
            )

            # Get measurement to verify it exists
            measurement = await self.measurement_service.get_measurement(measurement_id)
            if not measurement:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={
                        "success": False,
                        "message": f"Measurement with ID {measurement_id} not found",
                    },
                )

            # Get all files for this measurement
            files = await self.measurement_service.get_measurement_files(measurement_id)
            if not files:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={
                        "success": False,
                        "message": f"No files found for measurement ID {measurement_id}",
                    },
                )

            # Authenticate with Google Drive
            if not self.google_drive_service.ensure_authenticated():
                logger.error("Failed to authenticate with Google Drive")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "success": False,
                        "message": "Failed to authenticate with Google Drive",
                    },
                )

            # Create in-memory ZIP file
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                # Download each file and add to ZIP
                for file in files:
                    try:
                        # Download file content from Google Drive
                        file_content = self.google_drive_service.download_file(file.google_drive_file_id)
                        if file_content:
                            # Add to ZIP archive
                            zip_file.writestr(file.name, file_content)
                        else:
                            logger.warning(f"Failed to download file {file.name} (ID: {file.google_drive_file_id})")
                    except Exception as e:
                        logger.error(f"Error downloading file {file.name}: {str(e)}")
                        # Continue with other files even if one fails

            # Prepare response
            zip_buffer.seek(0)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            zip_filename = f"measurement_{measurement_id}_{timestamp}.zip"

            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
            )

        except Exception as e:
            logger.error(f"Error downloading measurement files: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "message": f"Failed to download measurement files: {str(e)}",
                },
            )

    @measurement_router.post(
        "/start",
        response_model=MeasurementStartResponse,
        summary="Start a new measurement",
        description="Manually initiates a new measurement process with required configuration",
    )
    async def start_measurement(
        self,
        config: MeasurementConfigCreateSchema = Body(...),
        current_user: TokenPayloadSchema = Depends(get_current_user)
    ) -> MeasurementStartResponse:
        """
        Start a new measurement manually.

        Triggers an immediate measurement using the provided configuration settings.
        This endpoint is useful for on-demand measurements outside the regular schedule.

        Parameters:
            - config: Required measurement configuration to use for this measurement
        """
        try:
            measurement = await self.start_measurement_logic(scheduled=False, config=config)
            return MeasurementStartResponse(
                success=True,
                message="Measurement started successfully",
                measurement=measurement,
            )
        except Exception as e:
            return MeasurementStartResponse(
                success=False, message=f"Failed to start measurement: {str(e)}"
            )

    async def start_measurement_logic(
        self, scheduled: bool = False, config: Union[MeasurementConfigSchema, MeasurementConfigCreateSchema] = None
    ) -> MeasurementInfoSchema:
        """
        Logic for starting a new measurement

        Can be called manually or by the scheduler

        Parameters:
            - scheduled: Whether this is a scheduled measurement or manually triggered
            - config: Configuration to use for this measurement (required for manual measurements, optional for scheduled)
        """
        logger.info(f"Starting measurement (scheduled: {scheduled})")

        try:
            # Get configuration - use provided config or fetch current configuration
            if config is None and scheduled:
                config = await self.settings_service.get_measurement_config()
            elif config is None:
                raise ValueError("Configuration is required for manual measurements")

            # Create new measurement record
            new_measurement = MeasurementInfoOrm(
                date_time=datetime.now(timezone.utc),
                rgb_camera=config.rgb_camera,
                multispectral_camera=config.multispectral_camera,
                number_of_sensors=config.number_of_sensors,
                length_of_ae=config.length_of_ae,
                scheduled=scheduled,
            )

            saved_measurement = await self.measurement_service.create_measurement(
                new_measurement
            )
            logger.info(f"Created measurement with ID: {saved_measurement.id}")

            # No need to manually initialize files list anymore

            # For scheduled measurements or when using full config schema
            if isinstance(config, MeasurementConfigSchema):
                # Use our new comprehensive method that handles cameras and files
                measurement = await self.measurement_service.start_measurement_by_config(config)
                if measurement:
                    schema = MeasurementInfoSchema.from_orm(measurement)
                    if hasattr(measurement, 'files') and measurement.files:
                        schema.files = []
                        for file in measurement.files:
                            file_schema = MeasurementFileSchema.from_orm(file)
                            schema.files.append({
                                "id": file_schema.id,
                                "name": file_schema.name,
                                "google_drive_file_id": file_schema.google_drive_file_id,
                                "measurement_id": file_schema.measurement_id,
                                "created_at": file_schema.created_at,
                                "updated_at": file_schema.updated_at
                            })
                    return schema

            # Otherwise use the traditional approach for backwards compatibility
            else:
                # Start camera measurements if enabled
                if config.rgb_camera:
                    await self.measurement_service.start_rgb_measurement(
                        saved_measurement.id,
                        saved_measurement.date_time,
                        config.length_of_ae,
                    )

                if config.multispectral_camera:
                    await self.measurement_service.start_multispectral_measurement(
                        saved_measurement.id, saved_measurement.date_time
                    )

            schema = MeasurementInfoSchema.from_orm(saved_measurement)
            if hasattr(saved_measurement, 'files') and saved_measurement.files:
                schema.files = []
                for file in saved_measurement.files:
                    file_schema = MeasurementFileSchema.from_orm(file)
                    schema.files.append({
                        "id": file_schema.id,
                        "name": file_schema.name,
                        "google_drive_file_id": file_schema.google_drive_file_id,
                        "measurement_id": file_schema.measurement_id,
                        "created_at": file_schema.created_at,
                        "updated_at": file_schema.updated_at
                    })
            return schema

        except Exception as e:
            logger.error(f"Error in measurement logic: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start measurement: {str(e)}",
            )
