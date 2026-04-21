from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v2_1_1.schemas import Session as SessionSchema
from app.models.session import (
    CdrDimension,
    ChargingPeriod,
    Session as OCPISessionDB,
    SessionStatus,
)

# Valid status transitions per OCPI 2.1.1.
# COMPLETED and INVALID are terminal — no outbound transitions allowed.
_VALID_TRANSITIONS: dict[SessionStatus, set[SessionStatus]] = {
    SessionStatus.PENDING: {SessionStatus.ACTIVE, SessionStatus.INVALID},
    SessionStatus.ACTIVE: {SessionStatus.COMPLETED, SessionStatus.INVALID},
    SessionStatus.COMPLETED: set(),
    SessionStatus.INVALID: set(),
}


class InvalidStatusTransition(ValueError):
    """Raised when a proposed session status transition is not permitted."""


class SessionNotFound(LookupError):
    """Raised when a session cannot be found for the given identity."""


class SessionService:
    """
    Service layer for OCPI 2.1.1 Session operations.

    All methods operate within the provided AsyncSession.  The caller is
    responsible for injecting a session and, where needed, for committing
    or rolling back outside the service (though the service commits
    internally after each successful write to keep things simple).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_transition(
        self, current: SessionStatus, proposed: SessionStatus
    ) -> None:
        """Raise InvalidStatusTransition if the proposed change is illegal."""
        if current == proposed:
            return
        allowed = _VALID_TRANSITIONS.get(current, set())
        if proposed not in allowed:
            allowed_values = [s.value for s in allowed] or ["none — terminal state"]
            raise InvalidStatusTransition(
                f"Cannot transition session from '{current.value}' to "
                f"'{proposed.value}'. Allowed: {allowed_values}"
            )

    async def _load(
        self, session_id: str, source_credentials_id: str
    ) -> Optional[OCPISessionDB]:
        """Fetch a session with all nested relationships eagerly loaded."""
        stmt = (
            select(OCPISessionDB)
            .where(
                OCPISessionDB.id == session_id,
                OCPISessionDB.source_credentials_id == source_credentials_id,
            )
            .options(
                selectinload(OCPISessionDB.charging_periods).selectinload(
                    ChargingPeriod.cdr_dimensions
                )
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _build_charging_periods(
        self,
        periods_data: list,
        session_id: str,
        source_credentials_id: str,
    ) -> list[ChargingPeriod]:
        """Convert raw charging period dicts or schema objects into ORM objects."""
        periods = []
        for p in periods_data:
            # Accept both dict (from PATCH) and Pydantic schema object (from PUT/POST)
            if isinstance(p, dict):
                start = p["start_date_time"]
                if isinstance(start, str):
                    start = datetime.fromisoformat(start.replace("Z", "+00:00"))
                dims_raw = p.get("cdr_dimensions", [])
            else:
                start = p.start_date_time
                dims_raw = p.cdr_dimensions or []

            cp = ChargingPeriod(
                session_id=session_id,
                session_source_credentials_id=source_credentials_id,
                start_date_time=start,
            )
            for d in dims_raw:
                if isinstance(d, dict):
                    cp.cdr_dimensions.append(
                        CdrDimension(type=d["type"], volume=d["volume"])
                    )
                else:
                    cp.cdr_dimensions.append(
                        CdrDimension(type=d.type, volume=d.volume)
                    )
            periods.append(cp)
        return periods

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_session(
        self, schema: SessionSchema, source_credentials_id: str
    ) -> OCPISessionDB:
        """
        Insert a new session with all nested charging periods and dimensions.
        Satisfies R1 / AC1.
        """
        db_session = OCPISessionDB(
            id=schema.id,
            source_credentials_id=source_credentials_id,
            start_datetime=schema.start_datetime,
            end_datetime=schema.end_datetime,
            kwh=schema.kwh,
            auth_id=schema.auth_id,
            auth_method=schema.auth_method,
            location_id=schema.location_id,
            evse_uid=schema.evse_uid,
            connector_id=schema.connector_id,
            meter_id=schema.meter_id,
            currency=schema.currency,
            total_cost=schema.total_cost,
            status=schema.status,
            # Preserve the CPO's last_updated on initial creation so that
            # date-range filtering (date_from / date_to) reflects the CPO's
            # record timestamp.  Updates and patches override with server time.
            last_updated=schema.last_updated,
        )

        for cp in self._build_charging_periods(
            schema.charging_periods or [], schema.id, source_credentials_id
        ):
            db_session.charging_periods.append(cp)

        self.db.add(db_session)
        await self.db.commit()

        # Re-fetch with relationships populated before returning
        return await self._load(db_session.id, source_credentials_id)

    async def get_session(
        self, session_id: str, source_credentials_id: str
    ) -> Optional[OCPISessionDB]:
        """
        Retrieve a single session with all nested objects populated.
        Returns None if not found.
        Satisfies R2 / AC2.
        """
        return await self._load(session_id, source_credentials_id)

    async def update_session(
        self,
        session_id: str,
        source_credentials_id: str,
        schema: SessionSchema,
    ) -> OCPISessionDB:
        """
        Full replacement (PUT semantics).  If the session exists, all fields
        and all charging periods are replaced.  If it doesn't exist, it is
        created (upsert behaviour matching OCPI 2.1.1 PUT).
        Satisfies R2 / AC3.
        """
        existing = await self._load(session_id, source_credentials_id)

        if existing is None:
            return await self.create_session(schema, source_credentials_id)

        # Validate status transition before touching the DB
        self._validate_transition(existing.status, SessionStatus(schema.status))

        # Clear the relationship list — the delete-orphan cascade removes the
        # rows from the DB.  Clearing via slice assignment also removes them
        # from the ORM identity map so they don't resurface on re-fetch.
        existing.charging_periods[:] = []
        await self.db.flush()

        # Overwrite scalar fields
        existing.start_datetime = schema.start_datetime
        existing.end_datetime = schema.end_datetime
        existing.kwh = schema.kwh
        existing.auth_id = schema.auth_id
        existing.auth_method = schema.auth_method
        existing.location_id = schema.location_id
        existing.evse_uid = schema.evse_uid
        existing.connector_id = schema.connector_id
        existing.meter_id = schema.meter_id
        existing.currency = schema.currency
        existing.total_cost = schema.total_cost
        existing.status = schema.status
        existing.last_updated = datetime.now(timezone.utc)

        # Attach new charging periods
        for cp in self._build_charging_periods(
            schema.charging_periods or [], session_id, source_credentials_id
        ):
            existing.charging_periods.append(cp)

        await self.db.commit()
        return await self._load(session_id, source_credentials_id)

    async def patch_session(
        self,
        session_id: str,
        source_credentials_id: str,
        patch: dict,
    ) -> Optional[OCPISessionDB]:
        """
        Partial update (PATCH semantics).
        - Top-level scalar fields: updated only if present in the patch.
        - charging_periods: APPENDED to the existing list, never replaced.
          (Per OCPI 2.1.1 spec — full replacement requires a PUT.)
        - last_updated is always refreshed on any successful patch.
        Returns None if the session does not exist.
        Satisfies R3 / AC4 / AC5.
        """
        existing = await self._load(session_id, source_credentials_id)
        if existing is None:
            return None

        # Validate status transition if the patch touches status
        if "status" in patch:
            new_status = SessionStatus(patch["status"])
            self._validate_transition(existing.status, new_status)

        # Apply scalar field updates — skip reserved / non-patchable fields
        _skip = {"charging_periods", "id", "source_credentials_id"}
        _datetime_fields = {"start_datetime", "end_datetime"}

        for key, value in patch.items():
            if key in _skip:
                continue
            if key in _datetime_fields and isinstance(value, str):
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            setattr(existing, key, value)

        # OCPI 2.1.1 §3.8: charging_periods in PATCH are appended, not replaced
        if "charging_periods" in patch and patch["charging_periods"]:
            for cp in self._build_charging_periods(
                patch["charging_periods"], session_id, source_credentials_id
            ):
                existing.charging_periods.append(cp)

        existing.last_updated = datetime.now(timezone.utc)
        await self.db.commit()
        return await self._load(session_id, source_credentials_id)

    async def list_sessions(
        self,
        date_from: datetime,
        date_to: Optional[datetime] = None,
        offset: int = 0,
        limit: int = 50,
        credentials_id: Optional[str] = None,
    ) -> tuple[list[OCPISessionDB], int]:
        """
        Return a paginated list of sessions and the total matching count.

        Filters:
          - last_updated >= date_from  (required)
          - last_updated <= date_to    (optional)
          - source_credentials_id      (optional — scopes to one CPO)

        Satisfies R4 / R5 / AC6.
        """
        filters = [OCPISessionDB.last_updated >= date_from]
        if date_to is not None:
            filters.append(OCPISessionDB.last_updated <= date_to)
        if credentials_id is not None:
            filters.append(OCPISessionDB.source_credentials_id == credentials_id)

        count_stmt = (
            select(func.count())
            .select_from(OCPISessionDB)
            .where(*filters)
        )
        total: int = (await self.db.execute(count_stmt)).scalar_one()

        data_stmt = (
            select(OCPISessionDB)
            .where(*filters)
            .options(
                selectinload(OCPISessionDB.charging_periods).selectinload(
                    ChargingPeriod.cdr_dimensions
                )
            )
            .offset(offset)
            .limit(limit)
        )
        rows = await self.db.execute(data_stmt)
        sessions = list(rows.scalars().all())

        return sessions, total
