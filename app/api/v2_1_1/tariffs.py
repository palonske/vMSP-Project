from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import joinedload
from sqlmodel import Session, select
from app.database import engine, get_session
from app.models import Tariff, PartnerProfile, TariffType, TariffElement, TariffRestriction, PriceComponent
from datetime import datetime
from app.api.v2_1_1.schemas import TariffRead

def fix_date(data_dict):
    date_str = data_dict.get("last_updated")
    if date_str and isinstance(date_str, str):
        data_dict["last_updated"] = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return data_dict

def process_tariff(raw_data: dict, cpo: PartnerProfile, session: Session):
    # 1. Validate the incoming data
    validated_tariff = TariffRead.model_validate(raw_data)
    tariff_id = validated_tariff.id

    # 2. Cleanup existing (utilizing Cascades)
    existing = session.exec(
        select(Tariff).where(
            Tariff.id == tariff_id,
            Tariff.country_code == cpo.country_code,
            Tariff.party_id == cpo.party_id
        )
    ).first()

    if existing:
        session.delete(existing)
        session.flush()
        session.expunge(existing)

    fix_date(raw_data)

    # 3. Build the Tree
    # We create the root object
    new_tariff = Tariff(
        id=validated_tariff.id,
        country_code=cpo.country_code,
        party_id=cpo.party_id,
        currency=validated_tariff.currency,
        type=validated_tariff.type,
        last_updated=validated_tariff.last_updated
    )

    for el_read in validated_tariff.elements:
        # Create the Element
        element_obj = TariffElement()

        # Add Restrictions if they exist
        if el_read.restrictions:
            res_data = el_read.restrictions.model_dump()
            element_obj.restrictions = TariffRestriction(**res_data)

        # Add Price Components
        for pc_read in el_read.price_components:
            pc_obj = PriceComponent(**pc_read.model_dump())
            element_obj.price_components.append(pc_obj)

        # Append Element to Tariff
        new_tariff.elements.append(element_obj)

    # 4. Save the whole tree
    session.add(new_tariff)
    session.flush()

    return new_tariff