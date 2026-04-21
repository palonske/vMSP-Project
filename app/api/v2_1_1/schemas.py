from datetime import datetime
from enum import Enum
from app.models.connector import ConnectorType
from pydantic import BaseModel, ConfigDict
from typing import List, Optional

from app.models.base import OCPIBaseModel
from app.models.evse import Status
from app.models.partner import PartnerProfile


# 1. Connector Schema (Plain Pydantic)
class ConnectorRead(OCPIBaseModel):
    model_config = ConfigDict(from_attributes=True) # The "Secret Sauce"

    id: str
    standard: ConnectorType
    format: str
    voltage: int
    last_updated: datetime  # Use str to ensure it serializes to ISO format

# 2. EVSE Schema
class EVSERead(OCPIBaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    status: Status
    last_updated: datetime
    connectors: List[ConnectorRead] = [] # Nested list

# 3. Location Schema
class LocationRead(OCPIBaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    address: str
    city: str
    country_code: str
    party_id: str
    last_updated: datetime
    evses: List[EVSERead] = [] # Nested list

class EVSEUpdate(OCPIBaseModel):
    # This MUST be the Enum class, not 'str'
    status: Optional[Status] = None


from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class PriceComponentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    type: str  # ENERGY, FLAT, PARKING_TIME, TIME
    price: float
    vat: Optional[float] = None
    step_size: int

class TariffRestrictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start_time: Optional[str] = None
    end_time: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    min_kwh: Optional[float] = None
    max_kwh: Optional[float] = None
    min_current: Optional[float] = None
    max_current: Optional[float] = None
    min_power: Optional[float] = None
    max_power: Optional[float] = None
    min_duration: Optional[int] = None
    max_duration: Optional[int] = None
    day_of_week: List[str] = []

class TariffElementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    price_components: List[PriceComponentRead]
    restrictions: Optional[TariffRestrictionRead] = None

class TariffRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    currency: str
    type: Optional[str] = None
    elements: List[TariffElementRead]
    last_updated: datetime

class InternalRegister(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    token_a: str
    versions_url: str
    version_detail_url: Optional[str] = None
    registered_version: Optional[str] = None

class PartnerSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    token_c: str  # This will be your TOKEN_C
    token_b: str
    token_a: str
    versions_url: str    # Your Versions URL
    roles: List[dict]
    business_details: dict
    party_id: str
    country_code: str


class SessionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    INVALID = "INVALID"
    PENDING = "PENDING"


class AuthMethod(str, Enum):
    AUTH_REQUEST = "AUTH_REQUEST"
    WHITELIST = "WHITELIST"


class DimensionType(str, Enum):
    ENERGY = "ENERGY"
    FLAT = "FLAT"
    MAX_CURRENT = "MAX_CURRENT"
    MIN_CURRENT = "MIN_CURRENT"
    PARKING_TIME = "PARKING_TIME"
    TIME = "TIME"


class CdrDimension(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    type: DimensionType
    volume: float


class ChargingPeriod(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start_date_time: datetime
    cdr_dimensions: List[CdrDimension]


class Session(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    kwh: float
    auth_id: str
    auth_method: AuthMethod
    location_id: str
    evse_uid: str
    connector_id: str
    meter_id: Optional[str] = None
    currency: str
    charging_periods: List[ChargingPeriod] = []
    total_cost: Optional[float] = None
    status: SessionStatus
    last_updated: datetime

ConnectorRead.model_rebuild()
EVSERead.model_rebuild()
LocationRead.model_rebuild()
TariffRead.model_rebuild()
PartnerSchema.model_rebuild()
InternalRegister.model_rebuild()
Session.model_rebuild()
