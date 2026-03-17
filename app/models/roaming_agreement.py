from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from enum import Enum
from app.models.base import OCPIBaseModel, DisplayText
from sqlmodel import SQLModel, Field, Column, Relationship, Enum as SQLEnum
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint


class AgreementStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"

class RoamingAgreement(OCPIBaseModel, table=True):

    id: Optional[int] = Field(default=None, primary_key=True)

    # eMSP Columns
    emsp_country_code: str = Field(index=True)
    emsp_party_id: str = Field(index=True)

    # CPO Columns
    cpo_country_code: str = Field(index=True)
    cpo_party_id: str = Field(index=True)

    status: AgreementStatus = Field(
        sa_column=Column(SQLEnum(AgreementStatus), default=AgreementStatus.ACTIVE)
    )

    # Permissions
    location_enabled: bool = Field(default=True)
    tariff_enabled: bool = Field(default=True)
    tokens_enabled: bool = Field(default=False)
    commands_enabled: bool = Field(default=True)
    sessions_enabled: bool = Field(default=True)
    cdrs_enabled: bool = Field(default=True)

    created_date: datetime
    last_updated: datetime

    __table_args__ = (
        # 1. Define the Foreign Key for eMSP
        ForeignKeyConstraint(
            ["emsp_country_code", "emsp_party_id"],
            ["partnerprofile.country_code", "partnerprofile.party_id"],
        ),
        # 2. Define the Foreign Key for CPO
        ForeignKeyConstraint(
            ["cpo_country_code", "cpo_party_id"],
            ["partnerprofile.country_code", "partnerprofile.party_id"],
        ),
        # 3. Prevent duplicate agreements between the same two partners
        UniqueConstraint(
            "emsp_country_code", "emsp_party_id",
            "cpo_country_code", "cpo_party_id",
            name="unique_roaming_pair"
        ),
    )
