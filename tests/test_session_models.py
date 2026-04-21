from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine
from pydantic import ValidationError
import pytest

from app.models.session import Session as OCPISessionDB
from app.api.v2_1_1.schemas import Session as OCPISession


def _build_test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
    SQLModel.metadata.create_all(engine)
    return engine


def test_session_model_round_trip_json():
    payload = {
        "id": "session-123",
        "start_datetime": "2026-04-20T10:00:00Z",
        "end_datetime": "2026-04-20T11:00:00Z",
        "kwh": 12.5,
        "auth_id": "auth-123",
        "auth_method": "AUTH_REQUEST",
        "location_id": "loc-1",
        "evse_uid": "evse-1",
        "connector_id": "1",
        "meter_id": "meter-1",
        "currency": "USD",
        "total_cost": 4.2,
        "status": "COMPLETED",
        "last_updated": "2026-04-20T11:05:00Z",
        "charging_periods": [
            {
                "start_date_time": "2026-04-20T10:15:00Z",
                "cdr_dimensions": [{"type": "ENERGY", "volume": 12.5}],
            }
        ],
    }

    model = OCPISession.model_validate(payload)
    serialized = model.model_dump(mode="json")

    assert serialized["id"] == payload["id"]
    assert serialized["auth_method"] == payload["auth_method"]
    assert serialized["status"] == payload["status"]
    assert serialized["charging_periods"][0]["cdr_dimensions"][0]["type"] == "ENERGY"
    assert serialized["last_updated"] == "2026-04-20T11:05:00Z"


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "NOT_A_STATUS"),
        ("auth_method", "BAD_AUTH"),
    ],
)
def test_session_enum_validation_rejects_invalid_values(field, value):
    payload = {
        "id": "session-123",
        "source_credentials_id": "cpo-creds-1",
        "start_datetime": "2026-04-20T10:00:00Z",
        "kwh": 1.0,
        "auth_id": "auth-123",
        "auth_method": "AUTH_REQUEST",
        "location_id": "loc-1",
        "evse_uid": "evse-1",
        "connector_id": "1",
        "currency": "USD",
        "status": "ACTIVE",
        "last_updated": "2026-04-20T11:05:00Z",
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        OCPISession.model_validate(payload)


def test_dimension_type_validation_rejects_invalid_value():
    payload = {
        "id": "session-123",
        "source_credentials_id": "cpo-creds-1",
        "start_datetime": "2026-04-20T10:00:00Z",
        "kwh": 1.0,
        "auth_id": "auth-123",
        "auth_method": "AUTH_REQUEST",
        "location_id": "loc-1",
        "evse_uid": "evse-1",
        "connector_id": "1",
        "currency": "USD",
        "status": "ACTIVE",
        "last_updated": "2026-04-20T11:05:00Z",
        "charging_periods": [
            {
                "session_id": "session-123",
                "session_source_credentials_id": "cpo-creds-1",
                "start_date_time": "2026-04-20T10:15:00Z",
                "cdr_dimensions": [{"charging_period_id": 1, "type": "BAD_DIMENSION", "volume": 1.0}],
            }
        ],
    }

    with pytest.raises(ValidationError):
        OCPISession.model_validate(payload)


def test_sessions_schema_indexes_and_foreign_keys():
    engine = _build_test_engine()
    inspector = inspect(engine)

    table_names = set(inspector.get_table_names())
    assert "sessions" in table_names
    assert "charging_periods" in table_names
    assert "cdr_dimensions" in table_names

    indexes = inspector.get_indexes("sessions")
    index_names = {idx["name"] for idx in indexes}
    assert "ix_sessions_auth_id" in index_names
    assert "ix_sessions_status" in index_names
    assert "ix_sessions_last_updated" in index_names
    assert "ix_sessions_start_datetime" in index_names

    charging_fks = inspector.get_foreign_keys("charging_periods")
    assert any(fk["referred_table"] == "sessions" for fk in charging_fks)

    cdr_fks = inspector.get_foreign_keys("cdr_dimensions")
    assert any(fk["referred_table"] == "charging_periods" for fk in cdr_fks)

    with Session(engine) as db:
        valid_session = OCPISession(
            id="session-1",
            start_datetime="2026-04-20T10:00:00Z",
            kwh=1.0,
            auth_id="auth-1",
            auth_method="AUTH_REQUEST",
            location_id="loc-1",
            evse_uid="evse-1",
            connector_id="1",
            currency="USD",
            status="ACTIVE",
            last_updated="2026-04-20T10:00:00Z",
        )
        db_obj = OCPISessionDB(
            id="session-1",
            source_credentials_id="cpo-1",
            start_datetime="2026-04-20T10:00:00Z",
            kwh=1.0,
            auth_id="auth-1",
            auth_method="AUTH_REQUEST",
            location_id="loc-1",
            evse_uid="evse-1",
            connector_id="1",
            currency="USD",
            status="ACTIVE",
            last_updated="2026-04-20T10:00:00Z",
        )
        db.add(db_obj)
        db.commit()

        db.execute(
            text(
                """
                INSERT INTO charging_periods (session_id, session_source_credentials_id, start_date_time)
                VALUES ('session-1', 'cpo-1', '2026-04-20T10:15:00Z')
                """
            )
        )
        db.commit()

        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    """
                    INSERT INTO charging_periods (session_id, session_source_credentials_id, start_date_time)
                    VALUES ('missing-session', 'missing-cpo', '2026-04-20T10:15:00Z')
                    """
                )
            )
            db.commit()
