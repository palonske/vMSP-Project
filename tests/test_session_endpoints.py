import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.api.v2_1_1.sessions import patch_session, put_session
from app.models.connector import Connector  # noqa: F401
from app.models.evse import EVSE  # noqa: F401
from app.models.location import Location  # noqa: F401
from app.models.partner import Endpoint  # noqa: F401
from app.models.partner import PartnerProfile, PartnerRole
from app.models.session import Session as OCPISessionDB  # noqa: F401


@pytest_asyncio.fixture(scope="function")
async def db():
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


def _partner() -> PartnerProfile:
    return PartnerProfile(
        country_code="US",
        party_id="ABC",
        role=PartnerRole.CPO,
        versions_url="https://example.com/versions",
        registered_version="2.1.1",
        status="ACTIVE",
    )


def _put_payload(**overrides):
    payload = {
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
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_put_session_upserts_session(db):
    resp = await put_session(
        country_code="US",
        party_id="ABC",
        session_id="session-1",
        session_data=_put_payload(
            charging_periods=[
                {
                    "start_date_time": "2026-04-20T10:30:00Z",
                    "cdr_dimensions": [{"type": "ENERGY", "volume": 5.0}],
                }
            ]
        ),
        partner=_partner(),
        session=db,
    )

    assert resp["status_code"] == 1000
    assert resp["data"].id == "session-1"

    stored = await db.get(OCPISessionDB, ("session-1", "US:ABC"))
    assert stored is not None
    assert stored.source_credentials_id == "US:ABC"


@pytest.mark.asyncio
async def test_put_session_rejects_partner_mismatch(db):
    with pytest.raises(HTTPException) as exc:
        await put_session(
            country_code="NL",
            party_id="ABC",
            session_id="session-1",
            session_data=_put_payload(),
            partner=_partner(),
            session=db,
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_patch_session_returns_404_when_missing(db):
    with pytest.raises(HTTPException) as exc:
        await patch_session(
            country_code="US",
            party_id="ABC",
            session_id="missing",
            patch_data={"kwh": 12.0},
            partner=_partner(),
            session=db,
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_patch_session_updates_fields_and_appends_periods(db):
    partner = _partner()
    await put_session(
        country_code="US",
        party_id="ABC",
        session_id="session-1",
        session_data=_put_payload(
            charging_periods=[
                {
                    "start_date_time": "2026-04-20T10:05:00Z",
                    "cdr_dimensions": [{"type": "ENERGY", "volume": 2.0}],
                }
            ]
        ),
        partner=partner,
        session=db,
    )

    resp = await patch_session(
        country_code="US",
        party_id="ABC",
        session_id="session-1",
        patch_data={
            "kwh": 9.5,
            "charging_periods": [
                {
                    "start_date_time": "2026-04-20T10:15:00Z",
                    "cdr_dimensions": [{"type": "TIME", "volume": 10.0}],
                }
            ],
        },
        partner=partner,
        session=db,
    )

    assert resp["status_code"] == 1000
    assert resp["data"].kwh == 9.5
    assert len(resp["data"].charging_periods) == 2


@pytest.mark.asyncio
async def test_patch_session_rejects_invalid_status_transition(db):
    partner = _partner()
    await put_session(
        country_code="US",
        party_id="ABC",
        session_id="session-1",
        session_data=_put_payload(status="COMPLETED"),
        partner=partner,
        session=db,
    )

    with pytest.raises(HTTPException) as exc:
        await patch_session(
            country_code="US",
            party_id="ABC",
            session_id="session-1",
            patch_data={"status": "ACTIVE"},
            partner=partner,
            session=db,
        )

    assert exc.value.status_code == 400
