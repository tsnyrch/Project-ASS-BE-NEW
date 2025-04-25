from fastapi import APIRouter, Depends, HTTPException
from fastapi_restful.cbv import cbv
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel

# Set up logging
logger = logging.getLogger(__name__)

# Create router
camera_router = APIRouter()

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

@cbv(camera_router)
class CameraController:
    def __init__(self):
        # Initialize any required services here
        pass

    @camera_router.get(
        "/camera/test", 
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
        "/camera/health", 
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