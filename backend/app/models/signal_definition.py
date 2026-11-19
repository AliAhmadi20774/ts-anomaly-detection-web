from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class SignalDefinition(BaseModel):
    """Define a signal belonging to one test, separately from measured values."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1)
    test_id: UUID
