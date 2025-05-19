import json
from pathlib import Path

import psycopg2
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from httpx import HTTPError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, NoResultFound, ProgrammingError
from starlette.exceptions import HTTPException

from app.config import exception_config as exh
from app.config.settings import Environment, get_database_settings, get_settings
from app.controllers.camera_controller import camera_router
from app.controllers.measurement_controller import measurement_router
from app.controllers.settings_controller import settings_router
from app.controllers.system_controller import system_router
from app.controllers.user_controller import user_router
from app.models.measurement import MeasurementConfigSchema
from app.services.cron_scheduler import CronScheduler
from app.services.settings_service import SettingsService
from app.utils import db_session

settings = get_settings()


def create_application() -> FastAPI:
    application = FastAPI(
        title="Fast Api Docker Poetry Docs",
        debug=False,
    )

    # Configure CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.ALLOWED_CORS_ORIGINS),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.environment == Environment.prod:
        application.openapi_url = None

    application.add_exception_handler(
        RequestValidationError, exh.req_validation_handler
    )
    application.add_exception_handler(ValidationError, exh.validation_handler)
    application.add_exception_handler(AttributeError, exh.attribute_error_handler)

    application.add_exception_handler(NoResultFound, exh.data_not_found_error_handler)
    application.add_exception_handler(IntegrityError, exh.sql_error_handler)
    application.add_exception_handler(ProgrammingError, exh.sql_error_handler)
    application.add_exception_handler(HTTPError, exh.http_error_handler)
    application.add_exception_handler(HTTPException, exh.http_exception_handler)

    # Include routers with their new prefixes
    application.include_router(system_router, prefix="/api")
    application.include_router(camera_router, prefix="/api")
    application.include_router(user_router, prefix="/api")
    application.include_router(measurement_router, prefix="/api")
    application.include_router(settings_router, prefix="/api")

    # Mount static files
    application.mount("/static", StaticFiles(directory="app/static"), name="static")

    @application.on_event("startup")
    async def initialize():
        print("Connecting to postgres...")
        dsn = get_database_settings().url
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.close()
        conn.close()
        print("Successfully connected to postgres...")

        # Migrate existing JSON config to database if needed
        await migrate_measurement_config()

        # Set up the scheduler based on the configuration
        await initialize_scheduler()

    @application.on_event("shutdown")
    async def shutdown():
        await db_session.shutdown()

    return application


async def migrate_measurement_config():
    """Migrate the measurement configuration from JSON file to the database if needed"""

    json_path = Path("data/measurement_config.json")

    # Skip if the file doesn't exist
    if not json_path.exists():
        print("No JSON configuration file found, skipping migration")
        return

    try:
        # Check if we already have configurations in the database
        settings_service = SettingsService()

        # Read the JSON file
        with open(json_path, "r") as f:
            config_data = json.load(f)

        # Create config schema
        config = MeasurementConfigSchema(**config_data)

        # Save to database
        await settings_service.update_measurement_config(config)

        # Rename the old file to prevent re-migration
        backup_path = json_path.with_suffix(".json.migrated")
        json_path.rename(backup_path)

        print("Successfully migrated measurement config from JSON to database")
        print(f"Original file backed up to {backup_path}")

    except Exception as e:
        print(f"Error during config migration: {str(e)}")


async def initialize_scheduler():
    """Initialize the measurement scheduler based on the database configuration"""

    try:
        # Get the current configuration from the database
        settings_service = SettingsService()
        config = await settings_service.get_measurement_config()

        # Configure the scheduler
        scheduler = CronScheduler.get_instance()
        scheduler.set_new_schedule(
            config.measurement_frequency, config.first_measurement, config.id
        )

        print(
            f"Scheduler initialized with frequency: {config.measurement_frequency} minutes"
        )
        print(
            f"First measurement scheduled for: {config.first_measurement.isoformat()}"
        )
    except Exception as e:
        print(f"Error initializing scheduler: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:create_application",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        access_log=True,
        reload=settings.app_reload,  # has to be false for tracing to work
    )
