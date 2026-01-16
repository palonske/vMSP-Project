from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from enum import Enum

from sqlalchemy import table

from app.models.base import OCPIBaseModel, DisplayText
from sqlmodel import SQLModel, Field, Column, JSON, Relationship

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.evse import EVSE



class ConnectorType(str, Enum):
    CHADEMO = "CHADEMO"
    DOMESTIC_A = "DOMESTIC_A"
    DOMESTIC_B = "DOMESTIC_B"
    DOMESTIC_C = "DOMESTIC_C"
    DOMESTIC_D = "DOMESTIC_D"
    DOMESTIC_E = "DOMESTIC_E"
    DOMESTIC_F = "DOMESTIC_F"
    DOMESTIC_G = "DOMESTIC_G"
    DOMESTIC_H = "DOMESTIC_H"
    DOMESTIC_I = "DOMESTIC_I"
    DOMESTIC_J = "DOMESTIC_J"
    DOMESTIC_K = "DOMESTIC_K"
    DOMESTIC_L = "DOMESTIC_L"
    IEC_60309_2_single_16 = "IEC_60309_2_single_16"
    IEC_60309_2_three_16 = "IEC_60309_2_three_16"
    IEC_60309_2_three_32 = "IEC_60309_2_three_32"
    IEC_60309_2_three_64 = "IEC_60309_2_three_64"
    IEC_62196_T1 = "IEC_62196_T1"
    IEC_62196_T1_COMBO = "IEC_62196_T1_COMBO"
    IEC_62196_T2 = "IEC_62196_T2"
    IEC_62196_T2_COMBO = "IEC_62196_T2_COMBO"
    IEC_62196_T3A = "IEC_62196_T3A"
    IEC_62196_T3C = "IEC_62196_T3C"
    TESLA_R = "TESLA_R"
    TESLA_S = "TESLA_S"

class Connector(OCPIBaseModel, table=True):
    id: str = Field(primary_key=True)
    standard: ConnectorType
    format: str  # e.g., "SOCKET", "CABLE"
    power_type: str  # e.g., "AC_3_PHASE"
    voltage: int
    amperage: int
    tariff_id: Optional[str] = Field(default=None)
    terms_and_conditions: Optional[str] = Field(default=None)
    last_updated: datetime

    evse_uid: str = Field(foreign_key="evse.uid")
    location_id: str = Field(foreign_key="location.id")
    evse: Optional["EVSE"] = Relationship(back_populates="connectors")
    location: Optional["Location"] = Relationship()

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True
    )