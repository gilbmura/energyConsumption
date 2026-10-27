"""Public JSON contract based on the four columns in pjme_clean.csv."""

from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
)


def parse_timestamp(value: object) -> datetime:
    # Preserve CSV clock labels until the team agrees on timezone handling.
    if isinstance(value, str):
        if "T" not in value and " " not in value:
            raise ValueError("Use a full ISO datetime, for example 2018-01-01T00:00:00")
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Invalid ISO datetime") from exc
    if not isinstance(value, datetime):
        raise ValueError("Use an ISO datetime string")
    if value.tzinfo is not None:
        raise ValueError("Use the dataset's local clock time without Z or a UTC offset")
    if value.year < 1000 or value.microsecond:
        raise ValueError("Datetime must be year 1000 or later, with whole-second precision")
    return value


Timestamp = Annotated[datetime, BeforeValidator(parse_timestamp)]
Number = Annotated[float, Field(strict=True, allow_inf_nan=False)]


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    Datetime: Timestamp
    PJME_MW: Annotated[Number, Field(ge=0)]
    was_imputed: StrictBool
    temperature_c: Number

    @field_validator("Datetime")
    @classmethod
    def hourly_timestamp(cls, value: datetime) -> datetime:
        if value.minute or value.second:
            raise ValueError("Energy records must fall exactly on an hourly boundary")
        return value
