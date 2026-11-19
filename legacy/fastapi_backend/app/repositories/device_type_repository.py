from uuid import UUID

from app.database import Database
from app.models.device_type import DeviceType


class DeviceTypeRepository:
    """Store and retrieve device types."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, device_type: DeviceType) -> DeviceType:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO device_types (id, name) VALUES (%s, %s)",
                (device_type.id, device_type.name),
            )
        return device_type

    def list_all(self) -> list[DeviceType]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT id, name FROM device_types ORDER BY name, id"
            ).fetchall()
        return [DeviceType(**dict(row)) for row in rows]

    def get(self, device_type_id: UUID) -> DeviceType | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT id, name FROM device_types WHERE id = %s",
                (device_type_id,),
            ).fetchone()
        return DeviceType(**dict(row)) if row is not None else None
