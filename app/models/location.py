from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from enum import Enum
from app.models.evse import EVSE
from app.models.base import OCPIBaseModel, DisplayText

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

class RegularHours(OCPIBaseModel):
    weekday: int
    period_begin: str
    period_end: str

class ExceptionalPeriod(OCPIBaseModel):
    period_begin: datetime
    period_end: datetime

class Hours(OCPIBaseModel):
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


class EnergySource(OCPIBaseModel):
    source: EnergySourceCategory
    percentage: int


class EnvironmentalImpactCategory(str, Enum):
    NUCLEAR_WASTE = "NUCLEAR_WASTE"
    CARBON_DIOXIDE = "CARBON_DIOXIDE"


class EnvironmentalImpact(OCPIBaseModel):
    source: EnvironmentalImpactCategory
    amount: int


class EnergyMix(OCPIBaseModel):
    is_green_energy: bool
    energy_sources: EnergySource
    environ_impact: EnvironmentalImpact
    supplier_name: str
    energy_product_name: str


class Location(OCPIBaseModel):
    id: str = Field(..., description="Unique ID for this location")
    type: LocationType
    name: Optional[str] = None
    address: str
    city: str
    postal_code: str
    country: str
    coordinates: GeoLocation

    # Nested Objects
    related_locations: Optional[List[GeoLocation]] = []
    evses: List['EVSE'] = []  # Assumes EVSE class is defined
    directions: Optional[List[DisplayText]] = []
    operator: Optional[BusinessDetails] = None
    suboperator: Optional[BusinessDetails] = None
    owner: Optional[BusinessDetails] = None
    facilities: Optional[Facility] = None
    images: Optional[List[Image]] = []
    opening_times: Optional[Hours] = None
    charging_when_closed: Optional[bool] = None
    energy_mix: Optional[EnergyMix] = None

    # DateTime logic
    last_updated: datetime
    timezone: Optional[str] = Field(None, description="e.g. 'Europe/Oslo'")

    class Config:
        # This ensures that when we export to JSON,
        # datetimes are formatted as ISO strings automatically.
        json_encoders = {
            datetime: lambda v: v.strftime('%Y-%m-%dT%H:%M:%SZ')
        }