from fastapi import APIRouter


class HealthController:
    """Expose the API liveness endpoint."""

    def __init__(self) -> None:
        self.router = APIRouter(tags=["Health"])
        self.router.add_api_route(
            path="/health",
            endpoint=self.check,
            methods=["GET"],
            summary="Check API health",
        )

    async def check(self) -> dict[str, str]:
        """Return the API liveness status."""
        return {"status": "ok"}
