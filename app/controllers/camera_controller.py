import base64
import logging
from typing import List, Optional

from fastapi import APIRouter, Query
from fastapi_restful.cbv import cbv
from pydantic import BaseModel

from app.services.aravis_camera_service import AravisCameraService

# Attempt to import Pillow (PIL) for image processing
try:
    from PIL import Image
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
    image_base64: Optional[str] = None
    image_format: Optional[str] = None  # e.g., "png"
    error: Optional[str] = None


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
    ) -> CaptureImageResponse:
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
                return CaptureImageResponse(
                    status="error",
                    device_id_used=camera_id,
                    message="Failed to connect to camera",
                    error="Could not establish connection with the camera",
                )

            try:
                # Get image as blob
                format = "PNG"  # Default format
                image_blob = camera_service.get_image_blob(format=format)

                if not image_blob:
                    return CaptureImageResponse(
                        status="error",
                        device_id_used=camera_id,
                        message="Failed to capture image",
                        error="Image capture operation returned no data",
                    )

                # Convert to base64
                base64_image = base64.b64encode(image_blob).decode("utf-8")

                return CaptureImageResponse(
                    status="success",
                    device_id_used=camera_id,
                    message="Image captured successfully",
                    image_base64=base64_image,
                    image_format=format.lower(),
                )
            finally:
                # Always disconnect from the camera when done
                camera_service.disconnect()

        except Exception as e:
            logger.error(f"Image capture error: {str(e)}")
            return CaptureImageResponse(
                status="error",
                device_id_used=camera_id,
                message=f"Error capturing image: {str(e)}",
                error=str(e),
            )
