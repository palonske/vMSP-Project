from pydantic import BaseModel, Field, ConfigDict, field_serializer
from datetime import datetime
from typing import List, Optional
from enum import Enum
from sqlmodel import SQLModel

class DisplayText(SQLModel):
    language: str
    text: str

class Image:
    url: str
    thumbnail: str
    category: ImageCategory
    type: str
    width: int
    height: int

class ImageCategory(str, Enum):
    CHARGER = "CHARGER"
    ENTRANCE = "ENTRANCE"
    LOCATION = "LOCATION"
    NETWORK = "NETWORK"
    OPERATOR = "OPERATOR"
    OTHER = "OTHER"
    OWNER = "OWNER"


class OCPIBaseModel(SQLModel):
    model_config = ConfigDict(
        validate_assignment=True,
        from_attributes=True
    )

    @field_serializer("*", mode="wrap")
    @classmethod
    def serialize_dt(cls, value, handler):
        """
        Global serializer that finds any datetime
        and ensures it ends with 'Z' for OCPI.
        """
        result = handler(value)
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%dT%H:%M:%SZ')
        return result


