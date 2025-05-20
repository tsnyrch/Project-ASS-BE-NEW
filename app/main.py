import psycopg2
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
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
from app.services.cron_scheduler import CronScheduler
from app.services.settings_service import SettingsService
from app.utils import db_session
from app.services.measurement_service import MeasurementService

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
    application.include_router(user_router, prefix="/api")
    application.include_router(measurement_router, prefix="/api")
    application.include_router(settings_router, prefix="/api")
    application.include_router(camera_router, prefix="/api")

    # Add catch-all routes for unknown endpoints with unique operation IDs
    @application.get("/{path_name:path}", operation_id="catch_all_get")
    @application.post("/{path_name:path}", operation_id="catch_all_post")
    @application.put("/{path_name:path}", operation_id="catch_all_put")
    @application.delete("/{path_name:path}", operation_id="catch_all_delete")
    @application.patch("/{path_name:path}", operation_id="catch_all_patch")
    @application.head("/{path_name:path}", operation_id="catch_all_head")
    @application.options("/{path_name:path}", operation_id="catch_all_options")
    async def catch_all(path_name: str):
        """Handle all unknown routes"""
        return {"detail": f"Endpoint '/{path_name}' not found", "status_code": 404}

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

        # Set up the scheduler based on the configuration
        await initialize_scheduler()

    @application.on_event("shutdown")
    async def shutdown():
        await db_session.shutdown()

    return application


async def initialize_scheduler():
    """Initialize the measurement scheduler based on the database configuration"""

    try:
        # Get the current configuration from the database
        settings_service = SettingsService()
        config = await settings_service.get_measurement_config()

        # Configure the scheduler
        scheduler = CronScheduler.get_instance()
        
        # Initialize services in the scheduler
        scheduler.measurement_service = MeasurementService()
        scheduler.settings_service = settings_service
        
        # Set up the schedule
        scheduler.set_new_schedule(
            config.measurement_frequency, config.first_measurement, config.id
        )

        print(
            f"Scheduler initialized with frequency: {config.measurement_frequency} minutes RGB: {config.rgb_camera} Multispectral: {config.multispectral_camera}"
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
        reload=settings.app_reload,
    )
