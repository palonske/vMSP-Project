"""
Tests for SessionService — covers all AC criteria from OCPI-3.

Uses an in-memory async SQLite database so tests are fully isolated
with no dependency on the application database file.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

# Ensure all table models are registered before create_all
from app.models.location import Location          # noqa: F401
from app.models.evse import EVSE                  # noqa: F401
from app.models.connector import Connector        # noqa: F401
from app.models.partner import PartnerProfile, Endpoint  # noqa: F401
from app.models.session import Session as OCPISessionDB, ChargingPeriod, CdrDimension  # noqa: F401

from app.api.v2_1_1.schemas import Session as SessionSchema
from app.services.session_service import (
    SessionService,
    InvalidStatusTransition,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="function")
async def db():
    """Provide a fresh in-memory async SQLite session per test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


def _make_schema(**overrides) -> SessionSchema:
    """Build a minimal valid SessionSchema, with optional field overrides."""
    defaults = {
        "id": "session-1",
        "start_datetime": "2026-04-20T10:00:00Z",
        "end_datetime": None,
        "kwh": 0.0,
        "auth_id": "auth-abc",
        "auth_method": "AUTH_REQUEST",
        "location_id": "loc-1",
        "evse_uid": "evse-1",
        "connector_id": "1",
        "meter_id": None,
        "currency": "USD",
        "total_cost": None,
        "status": "ACTIVE",
        "last_updated": "2026-04-20T10:00:00Z",
        "charging_periods": [],
    }
    defaults.update(overrides)
    return SessionSchema.model_validate(defaults)


# ---------------------------------------------------------------------------
# AC1: create_session persists session with nested charging periods / dimensions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_session_persists_session_and_nested_objects(db):
    schema = _make_schema(
        charging_periods=[
            {
                "start_date_time": "2026-04-20T10:05:00Z",
                "cdr_dimensions": [
                    {"type": "ENERGY", "volume": 5.0},
                    {"type": "TIME", "volume": 10.0},
                ],
            },
            {
                "start_date_time": "2026-04-20T10:30:00Z",
                "cdr_dimensions": [
                    {"type": "PARKING_TIME", "volume": 15.0},
                ],
            },
        ]
    )
    service = SessionService(db)
    result = await service.create_session(schema, source_credentials_id="cpo-1")

    assert result.id == "session-1"
    assert result.source_credentials_id == "cpo-1"
    assert result.auth_id == "auth-abc"
    assert len(result.charging_periods) == 2
    total_dims = sum(len(cp.cdr_dimensions) for cp in result.charging_periods)
    assert total_dims == 3


# ---------------------------------------------------------------------------
# AC2: get_session retrieves session with nested objects populated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_session_returns_nested_objects(db):
    service = SessionService(db)
    schema = _make_schema(
        charging_periods=[
            {
                "start_date_time": "2026-04-20T10:05:00Z",
                "cdr_dimensions": [{"type": "ENERGY", "volume": 7.5}],
            }
        ]
    )
    await service.create_session(schema, "cpo-1")

    fetched = await service.get_session("session-1", "cpo-1")

    assert fetched is not None
    assert fetched.id == "session-1"
    assert len(fetched.charging_periods) == 1
    assert fetched.charging_periods[0].cdr_dimensions[0].volume == 7.5


@pytest.mark.asyncio
async def test_get_session_returns_none_when_not_found(db):
    service = SessionService(db)
    result = await service.get_session("does-not-exist", "cpo-1")
    assert result is None


# ---------------------------------------------------------------------------
# AC3: update_session replaces all data including charging periods
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_session_replaces_charging_periods(db):
    service = SessionService(db)
    original = _make_schema(
        charging_periods=[
            {
                "start_date_time": "2026-04-20T10:05:00Z",
                "cdr_dimensions": [{"type": "ENERGY", "volume": 5.0}],
            }
        ]
    )
    await service.create_session(original, "cpo-1")

    updated_schema = _make_schema(
        status="COMPLETED",
        kwh=20.0,
        total_cost=8.50,
        charging_periods=[
            {
                "start_date_time": "2026-04-20T10:15:00Z",
                "cdr_dimensions": [{"type": "FLAT", "volume": 1.0}],
            },
            {
                "start_date_time": "2026-04-20T10:45:00Z",
                "cdr_dimensions": [{"type": "TIME", "volume": 30.0}],
            },
        ],
    )
    result = await service.update_session("session-1", "cpo-1", updated_schema)

    assert result.kwh == 20.0
    assert result.status.value == "COMPLETED"
    # Old period (ENERGY 5.0) must be gone; only the 2 new ones remain
    assert len(result.charging_periods) == 2
    dim_types = {
        d.type.value
        for cp in result.charging_periods
        for d in cp.cdr_dimensions
    }
    assert "ENERGY" not in dim_types
    assert "FLAT" in dim_types


@pytest.mark.asyncio
async def test_update_session_creates_when_not_found(db):
    service = SessionService(db)
    schema = _make_schema(id="brand-new")
    result = await service.update_session("brand-new", "cpo-1", schema)
    assert result.id == "brand-new"


# ---------------------------------------------------------------------------
# AC4: patch_session updates only the supplied fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_session_updates_only_supplied_fields(db):
    service = SessionService(db)
    schema = _make_schema(kwh=5.0, currency="EUR")
    await service.create_session(schema, "cpo-1")

    result = await service.patch_session(
        "session-1", "cpo-1", {"kwh": 15.5}
    )

    assert result.kwh == 15.5
    assert result.currency == "EUR"         # unchanged
    assert result.auth_id == "auth-abc"     # unchanged
    assert result.status.value == "ACTIVE"  # unchanged


@pytest.mark.asyncio
async def test_patch_session_returns_none_when_not_found(db):
    service = SessionService(db)
    result = await service.patch_session("ghost", "cpo-1", {"kwh": 1.0})
    assert result is None


# ---------------------------------------------------------------------------
# AC5: charging_periods in PATCH are appended, not replaced
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_session_appends_charging_periods(db):
    service = SessionService(db)
    schema = _make_schema(
        charging_periods=[
            {
                "start_date_time": "2026-04-20T10:05:00Z",
                "cdr_dimensions": [{"type": "ENERGY", "volume": 5.0}],
            }
        ]
    )
    await service.create_session(schema, "cpo-1")

    result = await service.patch_session(
        "session-1",
        "cpo-1",
        {
            "kwh": 12.0,
            "charging_periods": [
                {
                    "start_date_time": "2026-04-20T10:30:00Z",
                    "cdr_dimensions": [{"type": "TIME", "volume": 25.0}],
                }
            ],
        },
    )

    # Original period + 1 appended = 2 total
    assert len(result.charging_periods) == 2
    all_types = {
        d.type.value
        for cp in result.charging_periods
        for d in cp.cdr_dimensions
    }
    assert "ENERGY" in all_types   # original preserved
    assert "TIME" in all_types     # new one appended


# ---------------------------------------------------------------------------
# AC6: list_sessions respects date_from, limit, and returns total_count
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_sessions_pagination_and_total_count(db):
    service = SessionService(db)
    base_time = datetime(2026, 4, 20, 10, 0, 0, tzinfo=timezone.utc)

    for i in range(15):
        schema = _make_schema(
            id=f"session-{i}",
            last_updated=(base_time + timedelta(minutes=i)).isoformat().replace("+00:00", "Z"),
        )
        await service.create_session(schema, "cpo-1")

    sessions, total = await service.list_sessions(
        date_from=base_time,
        limit=10,
        offset=0,
    )

    assert total == 15
    assert len(sessions) == 10


@pytest.mark.asyncio
async def test_list_sessions_filters_by_credentials_id(db):
    service = SessionService(db)
    base_time = datetime(2026, 4, 20, 10, 0, 0, tzinfo=timezone.utc)

    for i in range(5):
        await service.create_session(_make_schema(id=f"cpo1-{i}"), "cpo-1")
    for i in range(3):
        await service.create_session(_make_schema(id=f"cpo2-{i}"), "cpo-2")

    sessions, total = await service.list_sessions(
        date_from=base_time - timedelta(seconds=1),
        credentials_id="cpo-1",
    )

    assert total == 5
    assert all(s.source_credentials_id == "cpo-1" for s in sessions)


@pytest.mark.asyncio
async def test_list_sessions_filters_by_date_to(db):
    service = SessionService(db)
    base_time = datetime(2026, 4, 20, 10, 0, 0, tzinfo=timezone.utc)

    for i in range(10):
        schema = _make_schema(
            id=f"session-{i}",
            last_updated=(base_time + timedelta(hours=i)).isoformat().replace("+00:00", "Z"),
        )
        await service.create_session(schema, "cpo-1")

    cutoff = base_time + timedelta(hours=4, minutes=30)
    sessions, total = await service.list_sessions(
        date_from=base_time,
        date_to=cutoff,
    )

    assert total == 5  # hours 0–4 inclusive


# ---------------------------------------------------------------------------
# AC7: Invalid enum values raise a validation error (on schema construction)
# ---------------------------------------------------------------------------

def test_invalid_auth_method_raises_validation_error():
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        _make_schema(auth_method="INVALID")


def test_invalid_status_raises_validation_error():
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        _make_schema(status="BOGUS")


# ---------------------------------------------------------------------------
# R6: Status transition validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_transition_completed_to_active_raises(db):
    service = SessionService(db)
    schema = _make_schema(status="ACTIVE")
    await service.create_session(schema, "cpo-1")
    # Move to COMPLETED via update
    await service.update_session("session-1", "cpo-1", _make_schema(status="COMPLETED"))

    with pytest.raises(InvalidStatusTransition):
        await service.update_session(
            "session-1", "cpo-1", _make_schema(status="ACTIVE")
        )


@pytest.mark.asyncio
async def test_invalid_transition_invalid_to_pending_raises(db):
    service = SessionService(db)
    schema = _make_schema(status="ACTIVE")
    await service.create_session(schema, "cpo-1")
    await service.update_session("session-1", "cpo-1", _make_schema(status="INVALID"))

    with pytest.raises(InvalidStatusTransition):
        await service.patch_session("session-1", "cpo-1", {"status": "PENDING"})


@pytest.mark.asyncio
async def test_valid_transitions_succeed(db):
    service = SessionService(db)
    await service.create_session(_make_schema(status="PENDING"), "cpo-1")

    result = await service.update_session(
        "session-1", "cpo-1", _make_schema(status="ACTIVE")
    )
    assert result.status.value == "ACTIVE"

    result = await service.update_session(
        "session-1", "cpo-1", _make_schema(status="COMPLETED")
    )
    assert result.status.value == "COMPLETED"