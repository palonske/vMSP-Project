from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from enum import Enum
from app.models.base import OCPIBaseModel, DisplayText
from sqlmodel import SQLModel, Field, Column, JSON, Relationship, Enum as SQLEnum
from sqlalchemy import and_, ForeignKey


class PartnerRole(str, Enum):
    CPO = "CPO"
    EMSP = "EMSP"
    HUB = "HUB"

class Endpoint(SQLModel, table=True):
    version: str = Field(primary_key=True)
    country_code: str = Field(foreign_key="partnerprofile.country_code", primary_key=True)
    party_id: str = Field(foreign_key="partnerprofile.party_id", primary_key=True)
    role: PartnerRole = Field(
        sa_column=Column(SQLEnum(PartnerRole),
            ForeignKey("partnerprofile.role"),
            primary_key=True
        ))

    partner: "PartnerProfile" = Relationship(back_populates="endpoints",
    sa_relationship_kwargs={
        "primaryjoin": "and_("
                        "Endpoint.country_code==PartnerProfile.country_code, "
                       "Endpoint.party_id==PartnerProfile.party_id, "
                        "Endpoint.role==PartnerProfile.role"
                        ")"
    })



    url: str
    identifier: str = Field(primary_key=True)

class PartnerProfile(SQLModel, table=True):
    # Composite Primary Key
    country_code: str = Field(primary_key=True, max_length=2)
    party_id: str = Field(primary_key=True, max_length=3)

    role: PartnerRole = Field(
        sa_column=Column(SQLEnum(PartnerRole), primary_key=True),
        default=PartnerRole.CPO
    )

    # Handshake Tokens
    token_c: Optional[str] = None  # Token YOU use to call THEM (for CPOs)
    token_b: Optional[str] = None  # Token THEY use to call YOU (for MSPs)
    token_a: Optional[str] = None  # Token used for versions/credentials module

    versions_url: str
    business_details: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    registered_version: str
    status: str = Field(default="REGISTERED") # REGISTERED, ACTIVE, SUSPENDED

    endpoints: List["Endpoint"] = Relationship(back_populates="partner", sa_relationship_kwargs={
        "primaryjoin": "and_("
                       "PartnerProfile.country_code==Endpoint.country_code, "
                       "PartnerProfile.party_id==Endpoint.party_id, "
                       "PartnerProfile.role==Endpoint.role"
                       ")"
    })