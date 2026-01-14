from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from enum import Enum

class OCPIBaseModel(BaseModel):
    class Config:
        # This ensures that when we export to JSON,
        # datetimes are formatted as ISO strings automatically.
        json_encoders = {
            datetime: lambda v: v.strftime('%Y-%m-%dT%H:%M:%SZ')
        }

    class DisplayText:
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