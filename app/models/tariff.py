from enum import Enum
from typing import List, Optional
from datetime import datetime

from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field, Relationship
from app.models.base import OCPIBaseModel

class TariffType(str, Enum):
    AD_HOC_PAYMENT = "AD_HOC_PAYMENT"
    PROFILE_CHECKOUT = "PROFILE_CHECKOUT"
    SUBSCRIPTION = "SUBSCRIPTION"

class PriceComponentType(str, Enum):
    ENERGY = "ENERGY"
    FLAT = "FLAT"
    PARKING_TIME = "PARKING_TIME"
    TIME = "TIME"

class DayOfWeek(str, Enum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"

class TariffRestriction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    element_id: int = Field(foreign_key="tariffelement.id", unique=True)

    # Timing Restrictions
    start_time: Optional[str] = None  # e.g., "13:30"
    end_time: Optional[str] = None    # e.g., "19:45"
    start_date: Optional[str] = None  # e.g., "2023-12-01"
    end_date: Optional[str] = None    # e.g., "2023-12-31"

    # Session Metrics
    min_kwh: Optional[float] = None
    max_kwh: Optional[float] = None
    min_current: Optional[float] = None # Amperes
    max_current: Optional[float] = None
    min_power: Optional[float] = None   # Watts
    max_power: Optional[float] = None
    min_duration: Optional[int] = None  # Seconds
    max_duration: Optional[int] = None

    # Days of the week (stored as JSON/List)
    # Note: SQLite doesn't have a native List type;
    # using SA_Relationship_kwargs or a simple string join is common.
    day_of_week: List[DayOfWeek] = Field(default=[], sa_column=Column(JSON))

    # Relationship back to the Element
    element: "TariffElement" = Relationship(back_populates="restrictions")

class PriceComponent(OCPIBaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    element_id: int = Field(foreign_key="tariffelement.id")

    type: PriceComponentType
    price: float  # The price without VAT
    vat: Optional[float] = None
    step_size: int = 1  # Minimum amount to charge (e.g., 1000 for 1kWh in OCPI units)

    element: "TariffElement" = Relationship(back_populates="price_components")

class TariffElement(OCPIBaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tariff_id: str = Field(foreign_key="tariff.id")

    # Relationships
    tariff: "Tariff" = Relationship(back_populates="elements")
    price_components: List["PriceComponent"] = Relationship(
        back_populates="element",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    restrictions: Optional["TariffRestriction"] = Relationship(
        back_populates="element",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

class Tariff(OCPIBaseModel, table=True):
    # OCPI Unique Keys
    id: str = Field(primary_key=True)
    country_code: str = Field(primary_key=True)
    party_id: str = Field(primary_key=True)

    tariff_alt_text: Optional[str] = None
    tariff_alt_url: Optional[str] = None
    energy_mix: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    currency: str  # e.g., "EUR", "USD"
    type: Optional[TariffType] = None

    # Metadata
    last_updated: datetime

    # Relationships
    elements: List["TariffElement"] = Relationship(
        back_populates="tariff",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )