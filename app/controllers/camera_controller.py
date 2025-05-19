from fastapi import APIRouter, Depends, HTTPException
from fastapi_restful.cbv import cbv
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel
import io
import base64
# Attempt to import Pillow (PIL) for image processing
try:
    from PIL import Image
except ImportError:
    Image = None # Pillow is not available

# Set up logging
logger = logging.getLogger(__name__)

# Create router
camera_router = APIRouter(
    prefix="/camera",
    tags=["camera"],
    responses={404: {"description": "Not found"}}
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
    image_format: Optional[str] = None # e.g., "png"
    error: Optional[str] = None

@cbv(camera_router)
class CameraController:
    def __init__(self):
        # Initialize any required services here
        pass

    @camera_router.get(
        "/test", 
        response_model=CameraTestResponse, 
        summary="Test Aravis camera connectivity",
        description="Tests the connection to Aravis cameras and returns detailed information about all connected devices"
    )
    def test_camera_connection(self) -> CameraTestResponse:
        """
        Test the connection to Aravis cameras.
        
        Returns information about all connected cameras including their model, vendor and serial number.
        This endpoint is useful for diagnosing camera connectivity issues.
        """
        try:
            # Import inside the function to avoid module loading issues at startup
            import os
            import gi
            
            # GI environment variables are already set in the Dockerfile
            gi.require_version('Aravis', '0.10')  # Using version 0.10 as installed in the container
            from gi.repository import Aravis

            logger.info("Scanning for camera devices...")
            Aravis.update_device_list()
            connected_num_device = Aravis.get_n_devices()
            logger.info(f"Device number: {connected_num_device}")
            
            result = CameraTestResponse(
                status="success",
                connected_devices=connected_num_device,
                devices=[]
            )
            
            if connected_num_device > 0:
                for i in range(connected_num_device):
                    device_info = CameraDeviceInfo(
                        index=i,
                        physical_id=Aravis.get_device_physical_id(i),
                        device_id=Aravis.get_device_id(i)
                    )
                    
                    try:
                        # Create a camera instance
                        camera = Aravis.Camera.new(device_info.device_id)
                        device_info.model = camera.get_model_name()
                        device_info.vendor = camera.get_vendor_name()
                        device_info.serial = camera.get_device_serial()
                        # Release the camera
                        camera = None
                    except Exception as e:
                        device_info.error = str(e)
                    
                    result.devices.append(device_info)
            
            return result
        except ImportError as e:
            logger.error(f"Aravis import error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to import Aravis: {str(e)}")
        except Exception as e:
            logger.error(f"Camera test error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Camera test failed: {str(e)}")

    @camera_router.get(
        "/health", 
        response_model=CameraHealthResponse,
        summary="Check camera system health",
        description="Performs a basic health check of the camera system"
    )
    def check_camera_health(self) -> CameraHealthResponse:
        """
        Check the health of the camera system.
        
        This is a simple endpoint that determines if the camera subsystem is operational.
        It can be used for monitoring and health checks.
        """
        return CameraHealthResponse(
            status="ok",
            message="Camera system is running"
        )

    @camera_router.post(
        "/capture",
        response_model=CaptureImageResponse,
        summary="Capture an image from an Aravis camera",
        description="Connects to an Aravis-compatible camera, captures a single frame, and returns it as a base64 encoded PNG.",
    )
    def capture_image(self, device_id: Optional[str] = None) -> CaptureImageResponse:
        """
        Captures a single image from an Aravis-compatible camera.

        Args:
            device_id: Optional. The specific ID of the camera to use. 
                       If None, the first available camera will be used.
                       It is recommended to specify a device_id for stable operation, 
                       which can be obtained from the /camera/test endpoint.

        Returns:
            A response containing the status, device_id used, an optional error message, 
            and the base64 encoded image if successful.
        """
        if Image is None:
            logger.error("Pillow (PIL) library is not installed. Image processing is not available.")
            raise HTTPException(status_code=500, detail="Pillow (PIL) library not installed. Cannot process image.")

        camera = None
        stream = None
        selected_device_id = None

        try:
            import gi
            gi.require_version('Aravis', '0.10')
            from gi.repository import Aravis

            Aravis.update_device_list()
            num_devices = Aravis.get_n_devices()

            if num_devices == 0:
                logger.warning("No Aravis cameras found.")
                return CaptureImageResponse(status="error", error="No Aravis cameras found.")

            if device_id:
                selected_device_id = device_id
                logger.info(f"Attempting to use specified camera: {selected_device_id}")
            else:
                # TODO: Implement more robust selection if multiple cameras are present and no device_id is given.
                # For now, using the first camera.
                selected_device_id = Aravis.get_device_id(0)
                logger.info(f"No device_id specified, using the first available camera: {selected_device_id}")
                # It's highly recommended to provide a specific device_id in a production environment
                # or if multiple cameras might be present.

            camera = Aravis.Camera.new(selected_device_id)
            if not camera:
                logger.error(f"Failed to create camera instance for device_id: {selected_device_id}")
                return CaptureImageResponse(status="error", device_id_used=selected_device_id, error=f"Failed to open camera {selected_device_id}.")

            logger.info(f"Successfully opened camera: {camera.get_model_name()} ({camera.get_vendor_name()}) - {camera.get_device_id()}")
            
            # --- Camera Configuration ---
            # TODO: Expose these as parameters or load from a configuration file.
            # Example: Set pixel format (Mono8 is common for monochrome)
            # available_formats = camera.dup_available_pixel_formats_as_strings()
            # logger.info(f"Available pixel formats: {available_formats}")
            # if "Mono8" in available_formats:
            #    camera.set_pixel_format_from_string("Mono8")
            # else:
            #    logger.warning("Mono8 pixel format not available. Using default.")
            # camera.set_pixel_format_from_string("BGR8") # Example for color, check camera for supported formats

            # Example: Set exposure time (in microseconds)
            # camera.set_exposure_time(10000) # 10ms

            # Example: Set gain
            # camera.set_gain(0)

            # Example: Set acquisition mode to SingleFrame for a single shot.
            # camera.set_acquisition_mode(Aravis.AcquisitionMode.SINGLE_FRAME)
            # camera.set_frame_count(1) # Ensure only one frame is captured

            # --- Image Acquisition ---
            # Using camera.acquisition() for a single blocking shot.
            # For continuous streaming, use camera.create_stream(), camera.start_acquisition(), stream.pop_buffer().
            logger.info("Starting image acquisition...")
            buffer = camera.acquisition(0) # 0 for no timeout (or use a sensible timeout in µs)

            if not buffer:
                logger.error("Failed to acquire image buffer.")
                return CaptureImageResponse(status="error", device_id_used=selected_device_id, error="Failed to acquire image buffer.")

            if buffer.get_status() != Aravis.BufferStatus.SUCCESS:
                logger.error(f"Buffer status not success: {buffer.get_status()}")
                return CaptureImageResponse(status="error", device_id_used=selected_device_id, error=f"Buffer acquisition failed with status: {buffer.get_status()}")

            logger.info("Image acquired successfully.")

            # --- Image Processing ---
            # Get image data (this is often a raw byte array)
            image_bytes = buffer.get_data()
            
            # Get image dimensions and format from the camera (after acquisition)
            width = camera.get_width()
            height = camera.get_height()
            pixel_format_str = camera.get_pixel_format_as_string()
            logger.info(f"Image details: {width}x{height}, Format: {pixel_format_str}")

            # Convert to Pillow Image object for easier processing/saving
            # This part needs to be adapted based on the actual pixel_format_str
            pil_image = None
            if pixel_format_str == "Mono8":
                pil_image = Image.frombytes("L", (width, height), image_bytes, "raw", "L", 0, 1)
            # TODO: Add more pixel format conversions as needed (e.g., BGR8, RGB8, Bayer formats etc.)
            # elif pixel_format_str == "BGR8": # Example
            #    pil_image = Image.frombytes("RGB", (width, height), image_bytes, "raw", "BGR", 0, 1)
            else:
                logger.warning(f"Unsupported pixel format for direct Pillow conversion: {pixel_format_str}. Returning raw bytes if possible, or error.")
                # For simplicity, we'll error out if not Mono8 for now.
                # In a real scenario, you might return raw bytes or try other conversions.
                return CaptureImageResponse(
                    status="error", 
                    device_id_used=selected_device_id,
                    error=f"Pixel format {pixel_format_str} not currently supported for conversion. Image data not processed."
                )

            if not pil_image:
                 return CaptureImageResponse(status="error", device_id_used=selected_device_id, error="Failed to create Pillow image from buffer.")

            # Convert to PNG and then to base64
            img_byte_arr = io.BytesIO()
            pil_image.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            image_base64 = base64.b64encode(img_byte_arr).decode('utf-8')

            logger.info("Image processed and encoded to base64 PNG.")

            return CaptureImageResponse(
                status="success",
                device_id_used=selected_device_id,
                message="Image captured successfully.",
                image_base64=image_base64,
                image_format="png"
            )

        except gi.RepositoryError as e:
            logger.error(f"Aravis/GObject Introspection error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Aravis GObject Introspection error: {str(e)}")
        except ImportError as e: # Should be caught by the initial check, but good to have.
            logger.error(f"Python library import error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Python library import error: {str(e)}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during image capture: {str(e)}", exc_info=True)
            # Check if selected_device_id was set
            device_info = selected_device_id if selected_device_id else "Unknown"
            return CaptureImageResponse(status="error", device_id_used=device_info, error=f"An unexpected error occurred: {str(e)}")
        finally:
            # Cleanup: Ensure camera and stream are released if they were created
            # In Python, GObjects are generally garbage collected, but explicit release can be good.
            # Setting to None helps ensure they are dereferenced.
            if stream:
                # If using stream.stop_buffer_queue() or similar, call here
                stream = None 
            if camera:
                # camera.stop_acquisition() # If using start_acquisition without camera.acquisition()
                camera = None # This should allow Python's GC to collect the GObject
            logger.info("Camera resources released.")