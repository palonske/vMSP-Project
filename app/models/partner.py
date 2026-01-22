from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from enum import Enum
from app.models.base import OCPIBaseModel, DisplayText
from sqlmodel import SQLModel, Field, Column, JSON, Relationship, Enum as SQLEnum

class PartnerRole(str, Enum):
    CPO = "CPO"
    EMSP = "EMSP"
    HUB = "HUB"

class PartnerProfile(SQLModel, table=True):
    # Composite Primary Key
    country_code: str = Field(primary_key=True, max_length=2)
    party_id: str = Field(primary_key=True, max_length=3)

    role: PartnerRole = Field(
        sa_column=Column(SQLEnum(PartnerRole)),
        default=PartnerRole.CPO
    )

    # Handshake Tokens
    token_c: Optional[str] = None  # Token YOU use to call THEM (for CPOs)
    token_b: Optional[str] = None  # Token THEY use to call YOU (for MSPs)
    token_a: Optional[str] = None  # Token used for versions/credentials module

    versions_url: str
    business_details: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    status: str = Field(default="REGISTERED") # REGISTERED, ACTIVE, SUSPENDED