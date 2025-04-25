import psycopg2
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from httpx import HTTPError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, ProgrammingError, NoResultFound
from starlette.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.config import exception_config as exh
from app.config.settings import Environment, get_settings, get_database_settings
from app.controllers.system_controller import system_router
from app.controllers.test_controller import test_router
from app.controllers.camera_controller import camera_router
from app.controllers.user_controller import user_router
from app.controllers.measurement_controller import measurement_router
from app.controllers.settings_controller import settings_router
from app.services.cron_scheduler import CronScheduler
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

    application.add_exception_handler(RequestValidationError, exh.req_validation_handler)
    application.add_exception_handler(ValidationError, exh.validation_handler)
    application.add_exception_handler(AttributeError, exh.attribute_error_handler)

    application.add_exception_handler(NoResultFound, exh.data_not_found_error_handler)
    application.add_exception_handler(IntegrityError, exh.sql_error_handler)
    application.add_exception_handler(ProgrammingError, exh.sql_error_handler)
    application.add_exception_handler(HTTPError, exh.http_error_handler)
    application.add_exception_handler(HTTPException, exh.http_exception_handler)

    # Include existing routers
    application.include_router(system_router)
    application.include_router(camera_router)

    # Include new routers
    application.include_router(user_router, prefix="/api")
    application.include_router(measurement_router, prefix="/api")
    application.include_router(settings_router, prefix="/api")

    if settings.is_local_dev:
        application.include_router(test_router)

    @application.on_event("startup")
    async def initialize():
        print(f"Connecting to postgres...")
        dsn = get_database_settings().url
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.close()
        conn.close()
        print(f"Successfully connected to postgres...")

    @application.on_event("shutdown")
    async def shutdown():
        await db_session.shutdown()

    return application


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
