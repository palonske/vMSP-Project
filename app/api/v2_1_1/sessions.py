from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v2_1_1.schemas import Session as SessionSchema
from app.core.authorization import validate_role
from app.core.utils import get_timestamp
from app.database import get_session
from app.models.partner import PartnerProfile, PartnerRole
from app.services.session_service import InvalidStatusTransition, SessionService

emsprouter = APIRouter()
cporouter = APIRouter()


def _source_credentials_id(partner: PartnerProfile) -> str:
    # Keep credentials identity deterministic per CPO until a dedicated
    # credentials table/ID is introduced.
    # TODO(OCPI-4 follow-up): if credentials_id storage format changes, this
    # requires a data migration for already persisted session PK/FK values.
    return f"{partner.country_code}:{partner.party_id}"


def _ocpi_error(message: str, ocpi_status_code: int = 2000) -> dict:
    return {
        "status_code": ocpi_status_code,
        "status_message": message,
        "timestamp": get_timestamp(),
    }


@emsprouter.put("/{country_code}/{party_id}/{session_id}")
async def put_session(
    country_code: str,
    party_id: str,
    session_id: str,
    session_data: dict,
    partner: PartnerProfile = Depends(validate_role(PartnerRole.CPO)),
    session: AsyncSession = Depends(get_session),
):
    if partner.party_id != party_id or partner.country_code != country_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path parameters do not match registered partner.",
        )

    if "id" in session_data and session_data["id"] != session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Body id does not match path session_id.",
        )

    session_data["id"] = session_id

    try:
        schema = SessionSchema.model_validate(session_data)
        service = SessionService(session)
        updated = await service.update_session(
            session_id=session_id,
            source_credentials_id=_source_credentials_id(partner),
            schema=schema,
        )
        return {
            "status_code": 1000,
            "status_message": "Session successfully updated/created",
            "timestamp": get_timestamp(),
            "data": SessionSchema.model_validate(updated),
        }
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_ocpi_error(str(exc), 2000),
        ) from exc
    except InvalidStatusTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_ocpi_error(str(exc), 2000),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_ocpi_error(f"Failed to process session: {exc}", 2000),
        ) from exc


@emsprouter.patch("/{country_code}/{party_id}/{session_id}")
async def patch_session(
    country_code: str,
    party_id: str,
    session_id: str,
    patch_data: dict,
    partner: PartnerProfile = Depends(validate_role(PartnerRole.CPO)),
    session: AsyncSession = Depends(get_session),
):
    if partner.party_id != party_id or partner.country_code != country_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path parameters do not match registered partner.",
        )

    if "id" in patch_data and patch_data["id"] != session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Body id does not match path session_id.",
        )

    try:
        service = SessionService(session)
        updated = await service.patch_session(
            session_id=session_id,
            source_credentials_id=_source_credentials_id(partner),
            patch=patch_data,
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )
        return {
            "status_code": 1000,
            "status_message": "Session patched successfully",
            "timestamp": get_timestamp(),
            "data": SessionSchema.model_validate(updated),
        }
    except InvalidStatusTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_ocpi_error(str(exc), 2000),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_ocpi_error(str(exc), 2000),
        ) from exc
