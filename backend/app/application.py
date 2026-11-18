from fastapi import FastAPI

from app.controllers.health_controller import HealthController


class Application:
    """Create the API and register its controllers."""

    def __init__(self) -> None:
        self.app = FastAPI(title="Anomaly Detection API", version="0.1.0")
        self.health_controller = HealthController()
        self.app.include_router(self.health_controller.router)
