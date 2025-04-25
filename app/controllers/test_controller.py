import asyncio

from fastapi import APIRouter, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi_restful.cbv import cbv
from pydantic import BaseModel

test_router = APIRouter(tags=["Testing"])

class TestSleepResponse(BaseModel):
    message: str
    sleep_duration_ms: int

@cbv(test_router)
class TestController:

    @test_router.get(
        "/test/sleep",
        include_in_schema=False,
        response_model=TestSleepResponse,
        summary="Test endpoint with delay",
        description="Test endpoint that simulates a delayed response"
    )
    async def sleep_test(self, duration_ms: int = 1000) -> TestSleepResponse:
        """
        Test endpoint that sleeps for the specified duration before responding.
        
        This endpoint is useful for testing timeout handling and async behavior.
        
        Parameters:
            - duration_ms: Sleep duration in milliseconds (default: 1000ms)
        """
        duration_sec = duration_ms / 1000
        await asyncio.sleep(duration_sec)
        return TestSleepResponse(
            message="Hello World!",
            sleep_duration_ms=duration_ms
        )

    @test_router.get(
        "/test/exception",
        include_in_schema=False,
        summary="Test exception handling",
        description="Test endpoint that always throws an exception"
    )
    async def exception_test(self) -> JSONResponse:
        """
        Test endpoint that always raises an exception.
        
        This endpoint is useful for testing error handling and logging.
        It deliberately throws a ValueError to trigger the exception handling middleware.
        """
        raise ValueError("This is an intentional test exception")
