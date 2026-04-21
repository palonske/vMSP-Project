from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from sqlalchemy import ForeignKeyConstraint, Index
from sqlmodel import Field, Relationship

from app.models.base import OCPIBaseModel


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


class Session(OCPIBaseModel, table=True):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_auth_id", "auth_id"),
        Index("ix_sessions_status", "status"),
        Index("ix_sessions_last_updated", "last_updated"),
        Index("ix_sessions_start_datetime", "start_datetime"),
    )

    id: str = Field(primary_key=True)
    source_credentials_id: str = Field(primary_key=True)

    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    kwh: float = Field(default=0.0)
    auth_id: str
    auth_method: AuthMethod
    location_id: str
    evse_uid: str
    connector_id: str
    meter_id: Optional[str] = None
    currency: str
    total_cost: Optional[float] = None
    status: SessionStatus = Field(default=SessionStatus.PENDING)
    last_updated: datetime

    # Hub metadata
    target_credentials_id: Optional[str] = None
    forwarding_status: str = Field(default="PENDING")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    charging_periods: List["ChargingPeriod"] = Relationship(
        back_populates="session",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class ChargingPeriod(OCPIBaseModel, table=True):
    __tablename__ = "charging_periods"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "session_source_credentials_id"],
            ["sessions.id", "sessions.source_credentials_id"],
            name="fk_charging_periods_sessions",
            ondelete="CASCADE",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str
    session_source_credentials_id: str
    start_date_time: datetime

    session: Optional[Session] = Relationship(back_populates="charging_periods")
    cdr_dimensions: List["CdrDimension"] = Relationship(
        back_populates="charging_period",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class CdrDimension(OCPIBaseModel, table=True):
    __tablename__ = "cdr_dimensions"

    id: Optional[int] = Field(default=None, primary_key=True)
    charging_period_id: int = Field(foreign_key="charging_periods.id")
    type: DimensionType
    volume: float

    charging_period: Optional[ChargingPeriod] = Relationship(back_populates="cdr_dimensions")


Session.model_rebuild()
ChargingPeriod.model_rebuild()
CdrDimension.model_rebuild()
