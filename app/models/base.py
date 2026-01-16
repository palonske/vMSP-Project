from pydantic import BaseModel, Field
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
    class Config:
        # This ensures that when we export to JSON,
        # datetimes are formatted as ISO strings automatically.
        json_encoders = {
            datetime: lambda v: v.strftime('%Y-%m-%dT%H:%M:%SZ')
        }

