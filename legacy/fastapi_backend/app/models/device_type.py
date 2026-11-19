from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class DeviceType(BaseModel):
    """Define a type of device independently of individual serial numbers."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1)
