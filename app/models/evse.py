from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from enum import Enum
from app.models.base import OCPIBaseModel, DisplayText
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

class StatusSchedule(OCPIBaseModel):
    period_begin: datetime
    period_end: Optional[datetime] = None
    status: Status

class GeoLocation(OCPIBaseModel):
    latitude: str
    longitude: str

class EVSE(OCPIBaseModel):
    uid: str = Field(..., description="Internal database ID of the EVSE")
    evse_id: Optional[str] = Field(None, description="Formal ID following ISO 15118")
    status: Status
    status_schedule: Optional[List['StatusSchedule']] = []
    capabilities: Optional[List['Capability']] = []
    coordinates: Optional[GeoLocation] = None
    physical_reference: Optional[str] = None
    connectors: List['Connector']
    directions: Optional[DisplayText] = None
    floor_level: Optional[str] = None
    coordinates: Optional[dict] = None
    last_updated: datetime

class Config:
    # This tells Pydantic to allow using the Connector class
    # even if it's defined later in the file
    arbitrary_types_allowed = True
    json_encoders = {
        datetime: lambda v: v.strftime('%Y-%m-%dT%H:%M:%SZ')
    }