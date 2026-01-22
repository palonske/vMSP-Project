from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from enum import Enum
from app.models.base import OCPIBaseModel, DisplayText
from sqlmodel import SQLModel, Field, Column, JSON, Relationship, Enum as SQLEnum

if TYPE_CHECKING:
    from app.models.evse import EVSE
    from app.models.connector import Connector

class BusinessDetails(BaseModel):
    name: str
    website: Optional[str] = None
    logo: Optional[dict] = None  # Contains 'url', 'thumbnail', etc.

class Image(BaseModel):
    url: str
    thumbnail: Optional[str] = None
    type: str  # e.g., "ENTRANCE", "LOCATION"
    width: Optional[int] = None
    height: Optional[int] = None

class GeoLocation(BaseModel):
    latitude: str
    longitude: str

class LocationType(str, Enum):
    ON_STREET = "ON_STREET"
    PARKING_GARAGE = "PARKING_GARAGE"
    UNDERGROUND_GARAGE = "UNDERGROUND_GARAGE"
    PARKING_LOT = "PARKING_LOT"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class Facility(str, Enum):
    HOTEL = "HOTEL"
    RESTAURANT = "RESTAURANT"
    CAFE = "CAFE"
    MALL = "MALL"
    SUPERMARKET = "SUPERMARKET"
    SPORT = "SPORT"
    RECREATION_AREA = "RECREATION_AREA"
    NATURE = "NATURE"
    MUSEUM = "MUSEUM"
    BUS_STOP = "BUS_STOP"
    TAXI_STAND = "TAXI_STAND"
    TRAIN_STATION = "TRAIN_STATION"
    AIRPORT = "AIRPORT"
    CARPOOL_PARKING = "CARPOOL_PARKING"
    FUEL_STATION = "FUEL_STATION"
    WIFI = "WIFI"

class RegularHours(BaseModel):
    weekday: int
    period_begin: str
    period_end: str

class ExceptionalPeriod(BaseModel):
    period_begin: datetime
    period_end: datetime

class Hours(BaseModel):
    regular_hours: RegularHours
    twentyfourseven: bool
    exceptional_openings: ExceptionalPeriod
    exceptional_closings: ExceptionalPeriod


class EnergySourceCategory(str, Enum):
    NUCLEAR = "NUCLEAR"
    GENERAL_FOSSIL = "GENERAL_FOSSIL"
    COAL = "COAL"
    GAS = "GAS"
    GENERAL_GREEN = "GENERAL_GREEN"
    SOLAR = "SOLAR"
    WIND = "WIND"
    WATER = "WATER"


class EnergySource(BaseModel):
    source: EnergySourceCategory
    percentage: int


class EnvironmentalImpactCategory(str, Enum):
    NUCLEAR_WASTE = "NUCLEAR_WASTE"
    CARBON_DIOXIDE = "CARBON_DIOXIDE"


class EnvironmentalImpact(BaseModel):
    source: EnvironmentalImpactCategory
    amount: int


class EnergyMix(BaseModel):
    is_green_energy: bool
    energy_sources: EnergySource
    environ_impact: EnvironmentalImpact
    supplier_name: str
    energy_product_name: str


class Location(OCPIBaseModel, table=True):
    id: str = Field(..., description="Unique ID for this location", primary_key=True)
    type: LocationType = Field(sa_column=Column(SQLEnum(LocationType)))
    name: Optional[str] = None
    address: str
    city: str
    postal_code: str
    country: str
    coordinates: dict = Field(default={}, sa_column=Column(JSON))
    country_code: str
    party_id: str

    # Nested Objects
    related_locations: Optional[List[dict]] = Field(default=[], sa_column=Column(JSON))
    evses: List['EVSE'] = Relationship(back_populates="location", sa_relationship_kwargs={"cascade": "all, delete-orphan"})  # Assumes EVSE class is defined
    directions: Optional[List[dict]] = Field(default=None, sa_column=Column(JSON))
    operator: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    suboperator: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    owner: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    facilities: Optional[List[Facility]] = Field(default=[], sa_column=Column(JSON))
    images: Optional[List[dict]] = Field(default=[], sa_column=Column(JSON))
    opening_times: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    charging_when_closed: Optional[bool] = Field(default=None)
    energy_mix: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # DateTime logic
    last_updated: datetime
    timezone: Optional[str] = Field(default=None)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True
    )