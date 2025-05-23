import asyncio
import logging
import os
from typing import Generator
from typing_extensions import AsyncGenerator

import alembic
import alembic.command
import alembic.config
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient

from app.main import create_application
from app.utils import db_session


@pytest.fixture(scope="session")
def app() -> FastAPI:
    return create_application()


@pytest_asyncio.fixture
async def async_client(app: FastAPI) -> AsyncGenerator:
    async with AsyncClient(app=app, base_url='http://test') as client:
        yield client


@pytest.fixture(autouse=True)
def run_migrations() -> Generator[None, None, None]:
    logging.getLogger('alembic').setLevel(logging.WARNING)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cfg = alembic.config.Config(os.path.join(project_root, "alembic.ini"))
    cfg.set_main_option(
        "script_location", os.path.join(project_root, "migrations")
    )
    alembic.command.upgrade(cfg, "head")
    yield
    alembic.command.downgrade(cfg, "base")
    """
    shutdown is needed to avoid this issue:
    got Future <Future pending cb=[Protocol._on_waiter_completed()]> attached to a different loop

    https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-multiple-asyncio-event-loops
    """
    asyncio.run(db_session.shutdown())
