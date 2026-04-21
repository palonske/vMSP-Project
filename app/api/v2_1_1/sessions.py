from fastapi import APIRouter, Depends, HTTPException, status
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
    return f"{partner.country_code}:{partner.party_id}"


@cporouter.put("/{country_code}/{party_id}/{session_id}")
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
    except InvalidStatusTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process session: {exc}",
        ) from exc


@cporouter.patch("/{country_code}/{party_id}/{session_id}")
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
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
