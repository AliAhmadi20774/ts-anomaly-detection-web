from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.models.device_type import DeviceType
from app.repositories.device_type_repository import DeviceTypeRepository
from app.schemas.device_type import DeviceTypeCreate


class DeviceTypeController:
    """Expose creation and retrieval of device types."""

    def __init__(self, repository: DeviceTypeRepository) -> None:
        self.repository = repository
        self.router = APIRouter(prefix="/device-types", tags=["Device types"])
        self.router.add_api_route(
            "", self.create, methods=["POST"], response_model=DeviceType,
            status_code=status.HTTP_201_CREATED,
            summary="Create a device type",
        )
        self.router.add_api_route(
            "", self.list_all, methods=["GET"], response_model=list[DeviceType],
            summary="List device types",
        )
        self.router.add_api_route(
            "/{device_type_id}", self.get, methods=["GET"],
            response_model=DeviceType,
            responses={404: {"description": "Device type not found"}},
            summary="Get a device type",
        )

    def create(self, payload: DeviceTypeCreate) -> DeviceType:
        return self.repository.create(DeviceType(name=payload.name))

    def list_all(self) -> list[DeviceType]:
        return self.repository.list_all()

    def get(self, device_type_id: UUID) -> DeviceType:
        device_type = self.repository.get(device_type_id)
        if device_type is None:
            raise HTTPException(status_code=404, detail="Device type not found")
        return device_type
