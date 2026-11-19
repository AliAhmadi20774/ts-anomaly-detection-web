from pydantic import BaseModel, ConfigDict, Field


class DeviceTypeCreate(BaseModel):
    """Accept a device type name; the server generates its identifier."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1)
