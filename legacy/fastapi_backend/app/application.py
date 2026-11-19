from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.controllers.device_type_controller import DeviceTypeController
from app.controllers.health_controller import HealthController
from app.database import Database
from app.repositories.device_type_repository import DeviceTypeRepository


class Application:
    """Create the API and register its controllers."""

    def __init__(self) -> None:
        self.database = Database()
        self.app = FastAPI(
            title="Anomaly Detection API", version="0.1.0", lifespan=self.lifespan
        )
        self.health_controller = HealthController()
        self.app.include_router(self.health_controller.router)
        self.device_type_repository = DeviceTypeRepository(self.database)
        self.device_type_controller = DeviceTypeController(self.device_type_repository)
        self.app.include_router(self.device_type_controller.router)

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncIterator[None]:
        self.database.initialize()
        yield
