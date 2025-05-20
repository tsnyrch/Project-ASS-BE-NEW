import logging
import os
from pathlib import Path
from typing import Optional, Union

import gi
import numpy as np
from PIL import Image

# Set up Aravis environment variables and import
# os.environ["GI_TYPELIB_PATH"] = (
#     "/usr/local/lib/x86_64-linux-gnu/girepository-1.0:/usr/lib/aarch64-linux-gnu/girepository-1.0"
# )
# os.environ["LD_LIBRARY_PATH"] = (
#     "/usr/local/lib/x86_64-linux-gnu:/usr/local/lib:"
#     + os.environ.get("LD_LIBRARY_PATH", "")
# )

# Load Aravis library
gi.require_version("Aravis", "0.10")
from gi.repository import Aravis  # noqa: E402


class AravisCameraService:
    """Service for interacting with cameras using the Aravis library."""

    def __init__(self, camera_id: Optional[str] = None, logger=None):
        """
        Initialize the Aravis Camera Service.

        Args:
            camera_id: Optional camera ID. If None, connects to the first available camera.
            logger: Optional logger object. If None, uses the standard logging module.
        """
        self.logger = logger or logging.getLogger(__name__)
        self.camera = None
        self.camera_id = camera_id
        self.stream = None

    def connect(self) -> bool:
        """Connect to the camera.

        Returns:
            bool: True if connection was successful, False otherwise.
        """
        try:
            # Initialize the Aravis library
            Aravis.update_device_list()

            # Connect to specific camera if ID provided, otherwise first available
            if self.camera_id:
                self.camera = Aravis.Camera.new(self.camera_id)
            else:
                self.camera = Aravis.Camera.new()

            if not self.camera:
                self.logger.error("No camera found")
                return False

            self.logger.info(f"Connected to camera: {self.camera.get_model_name()}")
            self.logger.info(f"Vendor: {self.camera.get_vendor_name()}")

            # Configure camera with default settings
            self._configure_camera()

            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to camera: {e}")
            return False

    def _configure_camera(self) -> None:
        """Configure the camera with optimized settings."""
        try:
            # Set acquisition mode to single frame
            self.camera.set_acquisition_mode(Aravis.AcquisitionMode.SINGLE_FRAME)

            # Optimize GigE Vision settings if applicable
            if self.camera.is_gv_device():
                self.camera.gv_auto_packet_size()
                packet_size = self.camera.gv_get_packet_size()
                self.logger.info(f"GigE packet size set to: {packet_size} bytes")

                # Enable packet resend
                try:
                    self.camera.gv_set_packet_resend(True)
                except Exception:
                    pass

            # Set optimal pixel format (preferring RGBA8 if available)
            pixel_formats = self.camera.dup_available_pixel_formats_as_strings()
            if pixel_formats:
                self.logger.info(f"Available pixel formats: {', '.join(pixel_formats)}")

                # Try to find RGBA format (for color image)
                rgba_formats = ["RGBA8", "BGRA8", "RGBa8", "BGRa8"]
                selected_format = None

                for fmt in rgba_formats:
                    if fmt in pixel_formats:
                        selected_format = fmt
                        break

                # Fall back to RGB if no RGBA format
                if not selected_format:
                    rgb_formats = ["RGB8", "BGR8"]
                    for fmt in rgb_formats:
                        if fmt in pixel_formats:
                            selected_format = fmt
                            break

                # Fall back to Mono8 or first available
                if not selected_format:
                    selected_format = (
                        "Mono8" if "Mono8" in pixel_formats else pixel_formats[0]
                    )

                self.camera.set_pixel_format_from_string(selected_format)
                self.logger.info(f"Using pixel format: {selected_format}")

            # Set reasonable exposure time
            if self.camera.is_exposure_time_available():
                min_exp, max_exp = self.camera.get_exposure_time_bounds()
                exposure = min_exp + (max_exp - min_exp) * 0.1  # Use 10% of range
                self.camera.set_exposure_time(exposure)
                self.logger.info(f"Set exposure time to {exposure} µs")

        except Exception as e:
            self.logger.warning(f"Camera configuration error: {e}")

    def _optimize_stream(self, stream) -> None:
        """Optimize GigE stream parameters for reliability."""
        if not isinstance(stream, Aravis.GvStream):
            return

        try:
            # Set larger socket buffer
            stream.set_property("socket-buffer-size", 30000000)  # 30MB

            # Enable packet resend
            stream.set_property("packet-resend", True)

            # Set reasonable timeouts
            stream.set_property("packet-timeout", 40000)  # 40ms
            stream.set_property("frame-retention", 200000)  # 200ms

        except Exception as e:
            self.logger.warning(f"Stream optimization error: {e}")

    def capture_image(self) -> Optional[np.ndarray]:
        """
        Capture a single image from the camera.

        Returns:
            np.ndarray: The captured image as a NumPy array, or None if capture failed.
        """
        if not self.camera:
            self.logger.error("No camera connected")
            return None

        try:
            # Get payload size for buffer creation
            payload = self.camera.get_payload()

            # Create a stream
            self.stream = self.camera.create_stream(None)
            if not self.stream:
                self.logger.error("Failed to create stream")
                return self._fallback_direct_acquisition()

            # Optimize stream settings
            self._optimize_stream(self.stream)

            # Create and push multiple buffers to the stream
            for _ in range(10):  # Increase buffer count for more reliable streaming
                buffer = Aravis.Buffer.new_allocate(payload)
                self.stream.push_buffer(buffer)

            # Start acquisition
            self.logger.info("Starting acquisition...")
            self.camera.start_acquisition()

            # Wait for buffer with timeout (increased to 10 seconds)
            self.logger.info("Waiting for buffer...")
            buffer = self.stream.timeout_pop_buffer(10000000)  # 10 seconds timeout

            if not buffer:
                self.logger.error(
                    "No buffer received within timeout, trying fallback method"
                )
                self._cleanup_acquisition()
                return self._fallback_direct_acquisition()

            # Check buffer status
            status = buffer.get_status()
            if status != Aravis.BufferStatus.SUCCESS:
                self.logger.error(f"Buffer status error: {status}")
                self._cleanup_acquisition()
                return self._fallback_direct_acquisition()

            # Process image data
            width = buffer.get_image_width()
            height = buffer.get_image_height()
            data = buffer.get_image_data()

            self.logger.info(f"Successfully captured image: {width}x{height}")

            # Use pixel format to determine array shape and type
            pixel_format = buffer.get_image_pixel_format()

            # Create numpy array from buffer data
            if "RGB" in str(pixel_format) or "BGR" in str(pixel_format):
                # RGB format - 3 channels
                image_array = np.frombuffer(data, dtype=np.uint8).reshape(
                    (height, width, 3)
                )
            elif "RGBA" in str(pixel_format) or "BGRA" in str(pixel_format):
                # RGBA format - 4 channels
                image_array = np.frombuffer(data, dtype=np.uint8).reshape(
                    (height, width, 4)
                )
            else:
                # Default to mono format
                image_array = np.frombuffer(data, dtype=np.uint8).reshape(
                    (height, width)
                )

            return image_array

        except Exception as e:
            self.logger.error(f"Image capture error: {e}")
            return self._fallback_direct_acquisition()
        finally:
            # Clean up
            self._cleanup_acquisition()

    def _fallback_direct_acquisition(self) -> Optional[np.ndarray]:
        """
        Fallback method using direct acquisition when stream method fails.

        Returns:
            np.ndarray: The captured image as a NumPy array, or None if capture failed.
        """
        self.logger.info("Trying fallback direct acquisition method...")
        try:
            # Make sure camera is in single frame mode
            self.camera.set_acquisition_mode(Aravis.AcquisitionMode.SINGLE_FRAME)

            # Get payload size and create buffer
            payload = self.camera.get_payload()
            buffer = Aravis.Buffer.new_allocate(payload)

            # Start acquisition
            self.camera.start_acquisition()

            # Acquire buffer with longer timeout (5 seconds)
            try:
                self.camera.acquisition(buffer, 5000000)
            except Exception as e:
                self.logger.error(f"Direct acquisition failed: {e}")
                return None

            # Check buffer status
            status = buffer.get_status()
            if status != Aravis.BufferStatus.SUCCESS:
                self.logger.error(f"Direct acquisition buffer status error: {status}")
                return None

            # Process image data
            width = buffer.get_image_width()
            height = buffer.get_image_height()
            data = buffer.get_image_data()

            self.logger.info(f"Direct acquisition successful: {width}x{height}")

            # Use pixel format to determine array shape and type
            pixel_format = buffer.get_image_pixel_format()

            # Create numpy array from buffer data
            if "RGB" in str(pixel_format) or "BGR" in str(pixel_format):
                # RGB format - 3 channels
                image_array = np.frombuffer(data, dtype=np.uint8).reshape(
                    (height, width, 3)
                )
            elif "RGBA" in str(pixel_format) or "BGRA" in str(pixel_format):
                # RGBA format - 4 channels
                image_array = np.frombuffer(data, dtype=np.uint8).reshape(
                    (height, width, 4)
                )
            else:
                # Default to mono format
                image_array = np.frombuffer(data, dtype=np.uint8).reshape(
                    (height, width)
                )

            return image_array

        except Exception as e:
            self.logger.error(f"Fallback acquisition error: {e}")
            return None
        finally:
            try:
                # Stop acquisition
                if self.camera:
                    self.camera.stop_acquisition()
            except Exception as e:
                self.logger.error(f"Error stopping camera in fallback: {e}")

    def get_image_blob(self, format: str = "PNG") -> Optional[bytes]:
        """
        Capture an image and return it as a binary blob.

        Args:
            format: Image format to use (PNG, JPEG, etc.)

        Returns:
            bytes: Image data as binary blob, or None if capture failed
        """
        image_array = self.capture_image()
        if image_array is None:
            return None

        try:
            # Convert numpy array to PIL Image
            if len(image_array.shape) == 2:
                # Grayscale image
                pil_image = Image.fromarray(image_array, "L")
            elif image_array.shape[2] == 3:
                # RGB image
                pil_image = Image.fromarray(image_array, "RGB")
            elif image_array.shape[2] == 4:
                # RGBA image
                pil_image = Image.fromarray(image_array, "RGBA")
            else:
                self.logger.error(f"Unsupported image shape: {image_array.shape}")
                return None

            # Save image to bytes buffer
            import io

            buffer = io.BytesIO()
            pil_image.save(buffer, format=format)
            return buffer.getvalue()

        except Exception as e:
            self.logger.error(f"Failed to create image blob: {e}")
            return None

    def save_image_file(self, filepath: Union[str, Path], format: str = None) -> bool:
        """
        Capture an image and save it to a file.

        Args:
            filepath: Path where to save the image
            format: Optional format override. If None, inferred from filepath extension

        Returns:
            bool: True if successful, False otherwise
        """
        image_array = self.capture_image()
        if image_array is None:
            return False

        try:
            # Convert numpy array to PIL Image
            if len(image_array.shape) == 2:
                # Grayscale image
                pil_image = Image.fromarray(image_array, "L")
            elif image_array.shape[2] == 3:
                # RGB image
                pil_image = Image.fromarray(image_array, "RGB")
            elif image_array.shape[2] == 4:
                # RGBA image
                pil_image = Image.fromarray(image_array, "RGBA")
            else:
                self.logger.error(f"Unsupported image shape: {image_array.shape}")
                return False

            # Save to file
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            pil_image.save(str(filepath), format=format)

            self.logger.info(f"Image saved to {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save image: {e}")
            return False

    def _cleanup_acquisition(self) -> None:
        """Clean up resources after acquisition."""
        try:
            # First clean up the stream if it exists
            if self.stream:
                # Try to pop all remaining buffers before stopping
                try:
                    for _ in range(10):
                        buffer = self.stream.try_pop_buffer()
                        if buffer is None:
                            break
                except Exception as e:
                    self.logger.debug(f"Error popping buffers: {e}")

                # Clear the stream reference
                local_stream = self.stream
                self.stream = None

                # Now it's safe to clean up the camera
                if self.camera:
                    try:
                        self.camera.stop_acquisition()
                    except Exception as e:
                        self.logger.debug(f"Error stopping acquisition: {e}")
            else:
                # Just stop the camera acquisition if no stream
                if self.camera:
                    try:
                        self.camera.stop_acquisition()
                    except Exception as e:
                        self.logger.debug(f"Error stopping acquisition: {e}")

        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")

    def disconnect(self) -> None:
        """Disconnect from the camera and cleanup resources."""
        self._cleanup_acquisition()
        self.camera = None
        self.stream = None
