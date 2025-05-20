import asyncio
import logging
from datetime import datetime

from app.models.measurement import MeasurementConfigSchema, MeasurementInfoOrm
from app.services.measurement_service_test import MeasurementServiceTest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_rgb_measurement():
    """Test RGB camera measurement using test image"""
    service = MeasurementServiceTest()
    
    # First, validate that test environment is set up properly
    if not service.validate_test_env():
        logger.error("Test environment validation failed. Cannot proceed with tests.")
        return
    
    # Create a test measurement
    measurement = MeasurementInfoOrm(
        date_time=datetime.utcnow(),
        rgb_camera=True,
        multispectral_camera=False,
        number_of_sensors=0,
        length_of_ae=0,
        scheduled=False
    )
    
    saved_measurement = await service.create_measurement(measurement)
    logger.info(f"Created test measurement with ID: {saved_measurement.id}")
    
    # Start RGB measurement
    result = await service.start_rgb_measurement(
        measurement_id=saved_measurement.id,
        date_time=saved_measurement.date_time,
        duration=5
    )
    
    logger.info(f"RGB measurement result: {result}")
    return result


async def test_multispectral_measurement():
    """Test multispectral camera measurement using test image"""
    service = MeasurementServiceTest()
    
    # Create a test measurement
    measurement = MeasurementInfoOrm(
        date_time=datetime.utcnow(),
        rgb_camera=False,
        multispectral_camera=True,
        number_of_sensors=0,
        length_of_ae=0,
        scheduled=False
    )
    
    saved_measurement = await service.create_measurement(measurement)
    logger.info(f"Created test measurement with ID: {saved_measurement.id}")
    
    # Start multispectral measurement
    result = await service.start_multispectral_measurement(
        measurement_id=saved_measurement.id,
        date_time=saved_measurement.date_time,
    )
    
    logger.info(f"Multispectral measurement result: {result}")
    return result


async def test_acoustic_measurement():
    """Test acoustic measurement using mock file"""
    service = MeasurementServiceTest()
    
    # Create a test measurement
    measurement = MeasurementInfoOrm(
        date_time=datetime.utcnow(),
        rgb_camera=False,
        multispectral_camera=False,
        number_of_sensors=2,
        length_of_ae=3.0,
        scheduled=False
    )
    
    saved_measurement = await service.create_measurement(measurement)
    logger.info(f"Created test measurement with ID: {saved_measurement.id}")
    
    # Start acoustic measurement
    result = await service.capture_acoustic_data(
        measurement_id=saved_measurement.id,
        number_of_sensors=2,
        length_of_ae=3.0
    )
    
    logger.info(f"Acoustic measurement result: {result}")
    return result


async def test_full_measurement_with_config():
    """Test full measurement with config"""
    service = MeasurementServiceTest()
    
    # Create a test config
    config = MeasurementConfigSchema(
        rgb_camera=True,
        multispectral_camera=True,
        number_of_sensors=2,
        length_of_ae=3.0
    )
    
    # Start measurement with config
    result = await service.start_measurement_by_config(config)
    
    if result:
        logger.info(f"Full measurement completed with ID: {result.id}")
        
        # Retrieve and verify files
        files = await service.get_measurement_files(result.id)
        logger.info(f"Found {len(files)} files for measurement {result.id}")
        for file in files:
            logger.info(f"- {file.name} (Google Drive ID: {file.google_drive_file_id})")
            
    return result


async def run_all_tests():
    """Run all test examples"""
    logger.info("Starting RGB measurement test...")
    await test_rgb_measurement()
    
    logger.info("\nStarting multispectral measurement test...")
    await test_multispectral_measurement()
    
    logger.info("\nStarting acoustic measurement test...")
    await test_acoustic_measurement()
    
    logger.info("\nStarting full measurement test...")
    await test_full_measurement_with_config()


if __name__ == "__main__":
    asyncio.run(run_all_tests())