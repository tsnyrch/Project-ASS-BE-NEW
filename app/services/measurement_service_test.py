import os
import io
import logging
from datetime import datetime
from typing import List, Tuple, Optional

from app.models.measurement import MeasurementInfoOrm, MeasurementInfoSchema, MeasurementConfigSchema
from app.models.measurement_file import MeasurementFileOrm, MeasurementFileSchema
from app.models.pageable import PageRequestSchema
from app.repository.measurement_repository import MeasurementRepository
from app.repository.measurement_file_repository import MeasurementFileRepository
from app.services.google_drive_service import GoogleDriveService

logger = logging.getLogger(__name__)


class MeasurementServiceTest:
    """
    Test version of the measurement service that doesn't use real cameras.
    
    This service is intended for testing purposes, replacing the real Aravis camera
    connections with local test image files. It maintains the same interface as the
    original MeasurementService, but doesn't require physical camera hardware.
    
    Use this service in test environments or when camera hardware is not available.
    """
    def __init__(self):
        self.measurement_repo = MeasurementRepository()
        self.file_repo = MeasurementFileRepository()
        self.test_image_path = "ae/test.png"
        self.ae_mock_file = "ae/ae.mock.txt"

    async def create_measurement(self, measurement: MeasurementInfoOrm) -> MeasurementInfoOrm:
        """
        Create a new measurement
        """
        return await self.measurement_repo.save_new_measurement(measurement)

    async def get_measurement(self, measurement_id: int) -> Optional[MeasurementInfoOrm]:
        """
        Get a measurement by ID
        """
        return await self.measurement_repo.get_measurement_by_id(measurement_id)
        
    async def get_measurement_with_files(self, measurement_id: int) -> Optional[MeasurementInfoOrm]:
        """
        Get a measurement by ID with files eager loaded
        
        Args:
            measurement_id: ID of the measurement
            
        Returns:
            MeasurementInfoOrm with files loaded or None if not found
        """
        measurement = await self.measurement_repo.get_measurement_by_id(measurement_id)
        # The relationship is configured with lazy="selectin", so files should be loaded
        return measurement

    async def get_latest_measurement_info(self) -> List[MeasurementInfoOrm]:
        """
        Get the latest measurements
        """
        return await self.measurement_repo.get_latest_measurement_info()
        
    async def get_latest_measurements_with_files(self) -> List[MeasurementInfoOrm]:
        """
        Get the latest measurements with files eager loaded
        
        Returns:
            List of MeasurementInfoOrm with files loaded
        """
        measurements = await self.measurement_repo.get_latest_measurement_info()
        # The relationship is configured with lazy="selectin", so files should be loaded
        return measurements

    async def get_measurement_history(self, start_date: datetime, end_date: datetime) -> List[MeasurementInfoOrm]:
        """
        Get measurement history within a date range
        """
        return await self.measurement_repo.get_measurement_history(start_date, end_date)
        
    async def get_measurement_history_with_files(self, start_date: datetime, end_date: datetime) -> List[MeasurementInfoOrm]:
        """
        Get measurement history within a date range with files eager loaded
        
        Args:
            start_date: Beginning of the date range
            end_date: End of the date range
            
        Returns:
            List of MeasurementInfoOrm with files loaded
        """
        measurements = await self.measurement_repo.get_measurement_history(start_date, end_date)
        # The relationship is configured with lazy="selectin", so files should be loaded
        return measurements

    async def delete_measurement(self, measurement: MeasurementInfoOrm) -> None:
        """
        Delete a measurement
        """
        await self.measurement_repo.delete_measurement(measurement)

    async def get_paged_measurements(self, pageable: PageRequestSchema) -> Tuple[List[MeasurementInfoOrm], int]:
        """
        Get paginated measurements
        """
        return await self.measurement_repo.get_paged_measurements(pageable)

    async def start_rgb_measurement(self, measurement_id: int, date_time: datetime, duration: int):
        """
        Start RGB camera measurement using test image instead of real camera

        Args:
            measurement_id: ID of the measurement
            date_time: Timestamp for the measurement
            duration: Duration of the measurement in seconds

        Returns:
            Status of the measurement
        """
        try:
            # Use test image instead of connecting to camera
            logger.info(f"Using test image {self.test_image_path} instead of RGB camera capture")
            
            # Check if the test image exists
            if not os.path.exists(self.test_image_path):
                logger.error(f"Test image not found: {self.test_image_path}")
                return {"status": "error", "message": f"Test image not found: {self.test_image_path}"}
            
            # Read test image content
            with open(self.test_image_path, 'rb') as f:
                image_blob = f.read()
            
            # Capture image as blob
            timestamp = date_time.strftime("%Y%m%d%H%M%S")
            rgb_filename = f"RGB_{timestamp}.png"
            format = "PNG"

            # Upload to Google Drive
            drive_service = GoogleDriveService()
            if not drive_service.authenticate():
                logger.error("Failed to authenticate with Google Drive")
                return {"status": "error", "message": "Failed to authenticate with Google Drive"}

            folder_path = f"/measurements/{measurement_id}"
            folder_id = drive_service.create_folder_path(folder_path)
            if not folder_id:
                logger.error(f"Failed to create folder for measurement {measurement_id}")
                return {"status": "error", "message": "Failed to create folder in Google Drive"}

            file_id = drive_service.upload_file_to_path(
                file_content=io.BytesIO(image_blob),
                file_name=rgb_filename,
                folder_path=folder_path,
                mime_type=f"image/{format.lower()}",
                is_path=False
            )

            if not file_id:
                logger.error("Failed to upload RGB image to Google Drive")
                return {"status": "error", "message": "Failed to upload image to Google Drive"}

            # Save file reference to the database with timestamps
            now = datetime.now()
            file = MeasurementFileOrm(
                name=rgb_filename,
                google_drive_file_id=file_id,
                measurement_id=measurement_id,
                created_at=now,
                updated_at=now
            )
            await self.file_repo.save(file)

            return {"status": "success", "message": f"RGB measurement {measurement_id} completed successfully", "file_id": file_id}

        except Exception as e:
            logger.error(f"Error during RGB measurement: {e}")
            return {"status": "error", "message": f"Error during RGB measurement: {str(e)}"}

    async def start_multispectral_measurement(self, measurement_id: int, date_time: datetime):
        """
        Start multispectral camera measurement using test image instead of real camera

        Args:
            measurement_id: ID of the measurement
            date_time: Timestamp for the measurement

        Returns:
            Status of the measurement
        """
        try:
            # Use test image instead of connecting to camera
            logger.info(f"Using test image {self.test_image_path} instead of multispectral camera capture")
            
            # Check if the test image exists
            if not os.path.exists(self.test_image_path):
                logger.error(f"Test image not found: {self.test_image_path}")
                return {"status": "error", "message": f"Test image not found: {self.test_image_path}"}
            
            # Read test image content
            with open(self.test_image_path, 'rb') as f:
                image_blob = f.read()
            
            # Capture image as blob
            timestamp = date_time.strftime("%Y%m%d%H%M%S")
            ms_filename = f"Multispectral_{timestamp}.png"
            format = "PNG"

            # Upload to Google Drive
            drive_service = GoogleDriveService()
            if not drive_service.authenticate():
                logger.error("Failed to authenticate with Google Drive")
                return {"status": "error", "message": "Failed to authenticate with Google Drive"}

            folder_path = f"/measurements/{measurement_id}"
            folder_id = drive_service.create_folder_path(folder_path)
            if not folder_id:
                logger.error(f"Failed to create folder for measurement {measurement_id}")
                return {"status": "error", "message": "Failed to create folder in Google Drive"}

            file_id = drive_service.upload_file_to_path(
                file_content=io.BytesIO(image_blob),
                file_name=ms_filename,
                folder_path=folder_path,
                mime_type=f"image/{format.lower()}",
                is_path=False
            )

            if not file_id:
                logger.error("Failed to upload multispectral image to Google Drive")
                return {"status": "error", "message": "Failed to upload image to Google Drive"}

            # Save file reference to the database with timestamps
            now = datetime.now()
            file = MeasurementFileOrm(
                name=ms_filename,
                google_drive_file_id=file_id,
                measurement_id=measurement_id,
                created_at=now,
                updated_at=now
            )
            await self.file_repo.save(file)

            return {"status": "success", "message": f"Multispectral measurement {measurement_id} completed successfully", "file_id": file_id}

        except Exception as e:
            logger.error(f"Error during multispectral measurement: {e}")
            return {"status": "error", "message": f"Error during multispectral measurement: {str(e)}"}

    async def capture_acoustic_data(self, measurement_id: int, number_of_sensors: int, length_of_ae: float):
        """
        Capture acoustic emission data using test file

        Args:
            measurement_id: ID of the measurement
            number_of_sensors: Number of acoustic sensors to use
            length_of_ae: Duration of acoustic capture in seconds

        Returns:
            Status of the acoustic capture
        """
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            drive_service = GoogleDriveService()

            if not drive_service.authenticate():
                logger.error("Failed to authenticate with Google Drive")
                return {"status": "error", "message": "Failed to authenticate with Google Drive"}

            folder_path = f"/measurements/{measurement_id}"
            folder_id = drive_service.create_folder_path(folder_path)

            if not folder_id:
                logger.error(f"Failed to create folder for measurement {measurement_id}")
                return {"status": "error", "message": "Failed to create folder in Google Drive"}

            file_ids = []

            # For each sensor, upload a mock file
            for sensor_id in range(1, number_of_sensors + 1):
                ae_filename = f"AE_sensor{sensor_id}_{timestamp}.txt"

                # Check if the mock file exists
                if not os.path.exists(self.ae_mock_file):
                    logger.error(f"Acoustic emission mock file not found: {self.ae_mock_file}")
                    return {"status": "error", "message": f"Mock data file not found: {self.ae_mock_file}"}
                
                # Read mock file content
                with open(self.ae_mock_file, 'rb') as f:
                    ae_content = f.read()

                # Upload to Google Drive
                file_id = drive_service.upload_file_to_path(
                    file_content=io.BytesIO(ae_content),
                    file_name=ae_filename,
                    folder_path=folder_path,
                    mime_type="text/plain",
                    is_path=False
                )

                if not file_id:
                    logger.error(f"Failed to upload acoustic data for sensor {sensor_id} to Google Drive")
                    return {"status": "error", "message": f"Failed to upload acoustic data for sensor {sensor_id}"}

                # Save file reference to the database with timestamps
                now = datetime.now()
                file = MeasurementFileOrm(
                    name=ae_filename,
                    google_drive_file_id=file_id,
                    measurement_id=measurement_id,
                    created_at=now,
                    updated_at=now
                )
                await self.file_repo.save(file)

                file_ids.append(file_id)

            return {"status": "success", "message": f"Acoustic data captured for {number_of_sensors} sensors", "file_ids": file_ids}

        except Exception as e:
            logger.error(f"Error capturing acoustic data: {e}")
            return {"status": "error", "message": f"Error capturing acoustic data: {str(e)}"}

    async def start_measurement_by_config(self, config: MeasurementConfigSchema) -> Optional[MeasurementInfoSchema]:
        """
        Start a new measurement based on the provided configuration

        Args:
            config: Measurement configuration

        Returns:
            The created measurement info if successful, None otherwise
        """
        try:
            # Create a new measurement record
            measurement = MeasurementInfoOrm(
                date_time=datetime.utcnow(),
                rgb_camera=config.rgb_camera,
                multispectral_camera=config.multispectral_camera,
                number_of_sensors=config.number_of_sensors,
                length_of_ae=config.length_of_ae,
                scheduled=True  # This is a scheduled measurement
            )

            # Save the measurement
            measurement = await self.measurement_repo.save_new_measurement(measurement)

            # Process each component based on configuration
            results = []
            
            logger.info(f"Starting test measurement with config: RGB={config.rgb_camera}, MS={config.multispectral_camera}, Sensors={config.number_of_sensors}")

            # RGB camera
            if config.rgb_camera:
                rgb_result = await self.start_rgb_measurement(
                    measurement_id=measurement.id,
                    date_time=measurement.date_time,
                    duration=int(config.length_of_ae)
                )
                results.append(rgb_result)

            # Multispectral camera
            if config.multispectral_camera:
                ms_result = await self.start_multispectral_measurement(
                    measurement_id=measurement.id,
                    date_time=measurement.date_time
                )
                results.append(ms_result)

            # Acoustic data
            if config.number_of_sensors > 0 and config.length_of_ae > 0:
                ae_result = await self.capture_acoustic_data(
                    measurement_id=measurement.id,
                    number_of_sensors=config.number_of_sensors,
                    length_of_ae=config.length_of_ae
                )
                results.append(ae_result)

            # Check if any component failed
            for result in results:
                if result.get("status") == "error":
                    logger.error(f"Measurement component failed: {result.get('message')}")
                    # We still return the measurement since some components might have succeeded

            return MeasurementInfoSchema.from_orm(measurement)

        except Exception as e:
            logger.error(f"Error starting measurement by config: {e}")
            return None

    def validate_test_env(self) -> bool:
        """
        Validates if test environment is properly set up by checking if required test files exist
        
        Returns:
            True if all required test files are present, False otherwise
        """
        files_to_check = [self.test_image_path, self.ae_mock_file]
        missing_files = []
        
        for file_path in files_to_check:
            if not os.path.exists(file_path):
                missing_files.append(file_path)
                
        if missing_files:
            logger.error(f"Test environment validation failed. Missing files: {', '.join(missing_files)}")
            return False
            
        logger.info("Test environment validation successful - all required test files present")
        return True
        
    async def get_measurement_files(self, measurement_id: int) -> List[MeasurementFileOrm]:
        """
        Get all files for a specific measurement
        
        Args:
            measurement_id: ID of the measurement
            
        Returns:
            List of measurement file records
        """
        return await self.file_repo.get_by_measurement_id(measurement_id)