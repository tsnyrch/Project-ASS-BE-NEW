import io
import logging
from datetime import datetime, timezone
from typing import Optional

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
    MeasurementHistorySchema,
    MeasurementInfoOrm,
    MeasurementInfoSchema,
    MeasurementLatestSchema,
)
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
            await self.measurement_service.get_latest_measurement_info() or []
        )
        planned_measurement = self.scheduler.next_scheduled_date

        latest_measurements_schema = [
            MeasurementInfoSchema.from_orm(m) for m in latest_measurements
        ]

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
        measurements_history = await self.measurement_service.get_measurement_history(
            start_date, end_date
        )
        measurements_schema = [
            MeasurementInfoSchema.from_orm(m) for m in measurements_history
        ]

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
        In a real implementation, this would return the measurement data files.

        Parameters:
            - measurement_id: The unique identifier for the measurement
        """
        measurement = await self.measurement_service.get_measurement(measurement_id)
        if not measurement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Measurement not found"
            )

        # This is a placeholder for the actual file generation and download
        # In a real implementation, you would generate or retrieve the measurement data files
        # and return them as a downloadable archive

        return MeasurementInfoSchema.from_orm(measurement)

    @measurement_router.post(
        "/upload-to-drive",
        response_model=FileUploadResponse,
        summary="Upload a file to Google Drive",
        description="Uploads a file to Google Drive in the /test/files/ directory",
        tags=["google-drive"],
    )
    async def upload_file_to_drive(
        self,
        file: UploadFile = File(...),
        current_user: TokenPayloadSchema = Depends(get_current_user),
    ) -> FileUploadResponse:
        """
        Upload a file to Google Drive.

        This endpoint uploads a file to Google Drive in the /test/files/ directory.

        Parameters:
            - file: The file to upload
        """
        try:
            logger.info(f"Starting Google Drive upload for file: {file.filename}")

            # Authenticate with Google Drive
            if not self.google_drive_service.ensure_authenticated():
                logger.error("Failed to authenticate with Google Drive")
                return FileUploadResponse(
                    success=False, message="Failed to authenticate with Google Drive"
                )

            # Read the file content
            file_content = await file.read()

            # Upload the file to Google Drive
            file_id = self.google_drive_service.upload_file_to_path(
                file_content=file_content,
                file_name=file.filename,
                folder_path="/test/files",
                mime_type=file.content_type,
            )

            if not file_id:
                return FileUploadResponse(
                    success=False, message="Failed to upload file to Google Drive"
                )

            return FileUploadResponse(
                success=True,
                message=f"File '{file.filename}' uploaded successfully to Google Drive",
                file_id=file_id,
            )

        except Exception as e:
            logger.error(f"Error uploading file to Google Drive: {e}")
            return FileUploadResponse(
                success=False, message=f"Failed to upload file: {str(e)}"
            )

    @measurement_router.post(
        "/download-from-drive",
        summary="Download a file from Google Drive",
        description="Downloads a file from Google Drive by file ID",
        tags=["google-drive"],
    )
    async def download_file_from_drive(
        self,
        request: FileDownloadRequest = Body(...),
        current_user: TokenPayloadSchema = Depends(get_current_user),
    ):
        """
        Download a file from Google Drive by its ID.

        This endpoint downloads a file from Google Drive using the provided file ID.

        Parameters:
            - file_id: The ID of the file to download
        """
        try:
            logger.info(
                f"Starting Google Drive download for file ID: {request.file_id}"
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

            # Get file metadata
            file_metadata = self.google_drive_service.get_file_metadata(request.file_id)
            if not file_metadata:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={
                        "success": False,
                        "message": f"File with ID {request.file_id} not found",
                    },
                )

            # Download the file
            file_content = self.google_drive_service.download_file(request.file_id)
            if not file_content:
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "success": False,
                        "message": "Failed to download file from Google Drive",
                    },
                )

            # Return the file as a streaming response
            file_name = file_metadata.get("name", "downloaded_file")
            mime_type = file_metadata.get("mimeType", "application/octet-stream")

            return StreamingResponse(
                io.BytesIO(file_content),
                media_type=mime_type,
                headers={"Content-Disposition": f"attachment; filename={file_name}"},
            )

        except Exception as e:
            logger.error(f"Error downloading file from Google Drive: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "message": f"Failed to download file: {str(e)}",
                },
            )

    @measurement_router.post(
        "/start",
        response_model=MeasurementStartResponse,
        summary="Start a new measurement",
        description="Manually initiates a new measurement process with optional configuration",
    )
    async def start_measurement(
        self, 
        config: Optional[MeasurementConfigSchema] = Body(None),
        current_user: TokenPayloadSchema = Depends(get_current_user)
    ) -> MeasurementStartResponse:
        """
        Start a new measurement manually.

        Triggers an immediate measurement using the provided configuration settings or the current settings if none are provided.
        This endpoint is useful for on-demand measurements outside the regular schedule.
    
        Parameters:
            - config: Optional measurement configuration to use for this measurement
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
        self, scheduled: bool = False, config: Optional[MeasurementConfigSchema] = None
    ) -> MeasurementInfoSchema:
        """
        Logic for starting a new measurement

        Can be called manually or by the scheduler

        Parameters:
            - scheduled: Whether this is a scheduled measurement or manually triggered
            - config: Optional configuration to use for this measurement instead of the stored config
        """
        logger.info(f"Starting measurement (scheduled: {scheduled})")

        try:
            # Get configuration - use provided config or fetch current configuration
            if config is None:
                config = await self.settings_service.get_measurement_config()

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

            return MeasurementInfoSchema.from_orm(saved_measurement)

        except Exception as e:
            logger.error(f"Error in measurement logic: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start measurement: {str(e)}",
            )
