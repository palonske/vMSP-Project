from datetime import datetime
from app.models.connector import ConnectorType
from pydantic import BaseModel, ConfigDict
from typing import List, Optional

from app.models.base import OCPIBaseModel
from app.models.evse import Status


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
    type: str  # ENERGY, FLAT, PARKING_TIME, TIME
    price: float
    vat: Optional[float] = None
    step_size: int

class TariffRestrictionRead(BaseModel):
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
    price_components: List[PriceComponentRead]
    restrictions: Optional[TariffRestrictionRead] = None

class TariffRead(BaseModel):
    id: str
    currency: str
    type: Optional[str] = None
    elements: List[TariffElementRead]
    last_updated: datetime

ConnectorRead.model_rebuild()
EVSERead.model_rebuild()
LocationRead.model_rebuild()
TariffRead.model_rebuild()