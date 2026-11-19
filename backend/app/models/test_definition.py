from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class TestDefinition(BaseModel):
    """Define a test belonging to one device type."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1)
    device_type_id: UUID
    sample_rate_hz: float = Field(gt=0, allow_inf_nan=False)
