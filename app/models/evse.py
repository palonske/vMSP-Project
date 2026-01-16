from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from enum import Enum
from app.models.base import OCPIBaseModel, DisplayText
from app.models.connector import Connector
from sqlmodel import SQLModel, Field, Column, JSON, Relationship

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.connector import Connector

# Statuses defined by OCPI 2.1.1
class Status(str, Enum):
    AVAILABLE = "AVAILABLE"
    BLOCKED = "BLOCKED"
    CHARGING = "CHARGING"
    INOPERATIVE = "INOPERATIVE"
    OUTOFORDER = "OUTOFORDER"
    PLANNED = "PLANNED"
    REMOVED = "REMOVED"
    RESERVED = "RESERVED"

class Capability(str, Enum):
    CHARGING_PROFILE_CAPABLE = "CHARGING_PROFILE_CAPABLE"
    CREDIT_CARD_PAYABLE = "CREDIT_CARD_PAYABLE"
    REMOTE_START_STOP_CAPABLE = "REMOTE_START_STOP_CAPABLE"
    RESERVABLE = "RESERVABLE"
    RFID_READER = "RFID_READER"
    UNLOCK_CAPABLE = "UNLOCK_CAPABLE"

class StatusSchedule(BaseModel):
    period_begin: datetime
    period_end: Optional[datetime] = None
    status: Status

class GeoLocation(BaseModel):
    latitude: str
    longitude: str

class EVSE(OCPIBaseModel, table=True):
    uid: str = Field(...,
                     description="Internal database ID of the EVSE",
                     primary_key=True)
    evse_id: Optional[str] = Field(None, description="Formal ID following ISO 15118")
    status: Status
    status_schedule: Optional[List[dict]] = Field(default=[], sa_column=Column(JSON))
    capabilities: Optional[List[Capability]] = Field(default=[], sa_column=Column(JSON))
    coordinates: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    physical_reference: Optional[str] = Field(default=None,)
    connectors: List['Connector'] = Relationship(back_populates="evse")
    directions: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    floor_level: Optional[str] = Field(default=None,)
    last_updated: datetime

    location_id: str = Field(foreign_key="location.id")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True
    )