import io
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, cast

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi_restful.cbv import cbv
from pydantic import BaseModel, Field

from app.services.aravis_camera_service import AravisCameraService
from app.services.measurement_service_test import MeasurementServiceTest

# Attempt to import Pillow (PIL) for image processing
try:
    from PIL import Image  # type: ignore
except ImportError:
    Image = None  # Pillow is not available

# Set up logging
logger = logging.getLogger(__name__)

# Create router
camera_router = APIRouter(
    prefix="/camera",
    tags=["camera"],
    responses={404: {"description": "Not found"}},
)


class CameraDeviceInfo(BaseModel):
    index: int
    physical_id: str
    device_id: str
    model: Optional[str] = None
    vendor: Optional[str] = None
    serial: Optional[str] = None
    error: Optional[str] = None


class CameraTestResponse(BaseModel):
    status: str
    connected_devices: int
    devices: List[CameraDeviceInfo]


class CameraHealthResponse(BaseModel):
    status: str
    message: str


class CaptureImageResponse(BaseModel):
    status: str
    device_id_used: Optional[str] = None
    message: Optional[str] = None
    image_path: Optional[str] = None
    image_format: Optional[str] = None  # e.g., "png"
    error: Optional[str] = None


class TestRunResponse(BaseModel):
    status: str
    message: str
    test_results: Optional[Dict[str, Any]] = None
    
    class Config:
        arbitrary_types_allowed = True


@cbv(camera_router)
class CameraController:
    def __init__(self):
        # Initialize any required services here
        pass

    @camera_router.get(
        "/capture",
        response_model=CaptureImageResponse,
        summary="Capture image from camera",
        description="Captures an image from an Aravis-compatible camera and returns it as a base64-encoded string",
    )
    def capture_image(
        self,
        camera_id: Optional[str] = Query(
            None, description="Optional camera ID to use for capture"
        ),
    ) -> StreamingResponse:
        """
        Capture an image from a connected camera.

        Returns the image as a base64-encoded string that can be displayed in browsers or saved.
        Optionally specify a camera ID if multiple cameras are connected.
        """
        try:
            # Create camera service with optional camera_id
            logger.info(
                f"Creating camera service{' with ID: ' + camera_id if camera_id else ''}"
            )
            camera_service = AravisCameraService(camera_id=camera_id, logger=logger)

            # Connect to camera
            if not camera_service.connect():
                return StreamingResponse(
                    io.BytesIO(b""),
                    media_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=error.json"},
                )

            try:
                # Get image as blob
                format = "PNG"  # Default format
                image_blob = camera_service.get_image_blob(format=format)

                if not image_blob:
                    return StreamingResponse(
                        io.BytesIO(b""),
                        media_type="application/json",
                        headers={
                            "Content-Disposition": "attachment; filename=error.json"
                        },
                    )

                # Return the file as a streaming response
                file_name = f"captured_image_{camera_id or 'default'}.{format.lower()}"
                mime_type = f"image/{format.lower()}"

                return StreamingResponse(
                    io.BytesIO(image_blob),
                    media_type=mime_type,
                    headers={
                        "Content-Disposition": f"attachment; filename={file_name}"
                    },
                )
            finally:
                # Always disconnect from the camera when done
                camera_service.disconnect()

        except Exception as e:
            logger.error(f"Image capture error: {str(e)}")
            return StreamingResponse(
                io.BytesIO(b""),
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=error.json"},
            )
            
    @camera_router.get(
        "/test",
        response_model=TestRunResponse,
        summary="Run measurement service tests",
        description="Runs all tests for the measurement service using test files instead of real cameras",
    )
    async def run_tests(
        self,
        test_type: Optional[str] = Query(
            "all", description="Test type to run (rgb, multispectral, acoustic, full, all)"
        ),
    ) -> JSONResponse:
        """
        Run measurement service tests.
        
        This endpoint triggers test runs of the measurement service using local test files
        instead of real camera connections. It's useful for testing the system without
        requiring physical camera hardware.
        
        Available test types:
        - rgb: Test RGB camera measurement
        - multispectral: Test multispectral camera measurement
        - acoustic: Test acoustic data capture
        - full: Test full measurement with all components
        - all: Run all tests (default)
        """
        try:
            # Create test service
            logger.info(f"Starting measurement service tests: {test_type}")
            service = MeasurementServiceTest()
            
            # Check if test environment is valid
            if not service.validate_test_env():
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "message": "Test environment validation failed. Missing required test files.",
                    },
                )
            
            results = {}
            
            # Run specified test or all tests
            if test_type in ["rgb", "all"]:
                logger.info("Running RGB camera test")
                
                # Create a test measurement for RGB
                from app.models.measurement import MeasurementInfoOrm
                rgb_measurement = MeasurementInfoOrm(
                    date_time=datetime.now(),
                    rgb_camera=True,
                    multispectral_camera=False,
                    number_of_sensors=0,
                    length_of_ae=0,
                    scheduled=False
                )
                rgb_measurement = await service.create_measurement(rgb_measurement)
                logger.info(f"Created RGB test measurement with ID: {rgb_measurement.id}")
                
                # Run RGB test with actual measurement ID
                rgb_result = await service.start_rgb_measurement(
                    measurement_id=rgb_measurement.id,
                    date_time=rgb_measurement.date_time,
                    duration=5
                )
                results["rgb_test"] = {**rgb_result, "measurement_id": rgb_measurement.id}
            
            if test_type in ["multispectral", "all"]:
                logger.info("Running multispectral camera test")
                
                # Create a test measurement for multispectral
                from app.models.measurement import MeasurementInfoOrm
                ms_measurement = MeasurementInfoOrm(
                    date_time=datetime.now(),
                    rgb_camera=False,
                    multispectral_camera=True,
                    number_of_sensors=0,
                    length_of_ae=0,
                    scheduled=False
                )
                ms_measurement = await service.create_measurement(ms_measurement)
                logger.info(f"Created multispectral test measurement with ID: {ms_measurement.id}")
                
                # Run multispectral test with actual measurement ID
                ms_result = await service.start_multispectral_measurement(
                    measurement_id=ms_measurement.id,
                    date_time=ms_measurement.date_time,
                )
                results["multispectral_test"] = {**ms_result, "measurement_id": ms_measurement.id}
                
            if test_type in ["acoustic", "all"]:
                logger.info("Running acoustic test")
                
                # Create a test measurement for acoustic
                from app.models.measurement import MeasurementInfoOrm
                acoustic_measurement = MeasurementInfoOrm(
                    date_time=datetime.now(),
                    rgb_camera=False,
                    multispectral_camera=False,
                    number_of_sensors=2,
                    length_of_ae=3.0,
                    scheduled=False
                )
                acoustic_measurement = await service.create_measurement(acoustic_measurement)
                logger.info(f"Created acoustic test measurement with ID: {acoustic_measurement.id}")
                
                # Run acoustic test with actual measurement ID
                acoustic_result = await service.capture_acoustic_data(
                    measurement_id=acoustic_measurement.id,
                    number_of_sensors=2,
                    length_of_ae=3.0
                )
                results["acoustic_test"] = {**acoustic_result, "measurement_id": acoustic_measurement.id}
                
            if test_type in ["full", "all"]:
                logger.info("Running full measurement test")
                # Creating a simplified config for testing purposes
                # This avoids complicated validation with the actual schema
                test_config = {
                    "rgb_camera": True,
                    "multispectral_camera": True,
                    "number_of_sensors": 2,
                    "length_of_ae": 3.0,
                    "measurement_frequency": 5,  # Every 5 minutes
                    "first_measurement": datetime.now() + timedelta(minutes=1)
                }
                
                # Use the actual schema
                from app.models.measurement import MeasurementConfigSchema
                config = MeasurementConfigSchema(**test_config)
                
                full_result = await service.start_measurement_by_config(config)
                
                if full_result:
                    results["full_test"] = {
                        "status": "success",
                        "measurement_id": full_result.id,
                        "rgb_camera": full_result.rgb_camera,
                        "multispectral_camera": full_result.multispectral_camera,
                        "number_of_sensors": full_result.number_of_sensors
                    }
                else:
                    results["full_test"] = {
                        "status": "error",
                        "message": "Full measurement test failed"
                    }
            
            # For all test types, also return file counts
            if results:
                for test_name, test_result in results.items():
                    if 'measurement_id' in test_result:
                        measurement_id = test_result['measurement_id']
                        files = await service.get_measurement_files(measurement_id)
                        test_result['files_count'] = len(files)
                        test_result['files'] = [
                            {"name": file.name, "id": file.id} 
                            for file in files[:5]  # Limiting to first 5 files
                        ]
            
            return JSONResponse(
                content={
                    "status": "success",
                    "message": f"Completed {test_type} tests",
                    "test_results": results
                }
            )
            
        except Exception as e:
            logger.error(f"Test execution error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": f"Error running tests: {str(e)}",
                },
            )
