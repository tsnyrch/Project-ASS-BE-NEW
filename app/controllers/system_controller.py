from fastapi import status, APIRouter
from fastapi.responses import JSONResponse
from fastapi_restful.cbv import cbv
from pydantic import BaseModel

system_router = APIRouter()

class HealthCheckResponse(BaseModel):
    status: str
    service: str
    code: int

class WelcomeResponse(BaseModel):
    message: str

@cbv(system_router)
class SystemController:

    @system_router.get(
        "/", 
        include_in_schema=False,
        response_model=WelcomeResponse
    )
    async def root(self) -> WelcomeResponse:
        """Display welcome message."""
        return WelcomeResponse(message="Hello World!")

    @system_router.get(
        "/health", 
        include_in_schema=False,
        response_model=HealthCheckResponse
    )
    async def healthcheck(self) -> JSONResponse:
        """Health check endpoint for monitoring and load balancers."""
        data = HealthCheckResponse(
            status="ok",
            service="fast-api-docker-poetry",
            code=status.HTTP_200_OK
        )
        return JSONResponse(data.dict(), status_code=status.HTTP_200_OK)
