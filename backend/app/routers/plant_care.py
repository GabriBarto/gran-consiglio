"""
AI "scheda di recupero pianta" endpoints: the species catalog the app
shows in its picker, and the sheet generation itself (species from the
catalog and/or a photo, plus an optional free-text symptom description).
See app/plant_care.py for the identification/generation pipeline.
"""
from __future__ import annotations

import mimetypes
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from .. import plant_care
from ..config import settings
from ..database import User
from ..dependencies import get_current_user
from ..schemas import IdentificationSource, PlantSpeciesPublic, RecoverySheetPublic

router = APIRouter(prefix="/plant-care", tags=["plant-care"])

MAX_SYMPTOMS_LENGTH = 1000


@router.get("/species", response_model=List[PlantSpeciesPublic])
def list_species() -> List[PlantSpeciesPublic]:
    return [
        PlantSpeciesPublic(id=s.id, common_name=s.common_name, scientific_name=s.scientific_name)
        for s in plant_care.SPECIES_CATALOG
    ]


@router.post("/recovery-sheet", response_model=RecoverySheetPublic)
async def create_recovery_sheet(
    species_id: Optional[str] = Form(None, description="Id da GET /plant-care/species"),
    symptoms: Optional[str] = Form(None, description="Descrizione libera dei sintomi (opzionale)"),
    photo: Optional[UploadFile] = File(None, description="Foto della pianta (JPEG, PNG o WebP)"),
    user: User = Depends(get_current_user),
) -> RecoverySheetPublic:
    """Login required: every call costs real AI-provider credits."""
    species = None
    if species_id:
        species = plant_care.get_species(species_id)
        if species is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Specie non presente nell'elenco.")

    symptoms = (symptoms or "").strip() or None
    if symptoms and len(symptoms) > MAX_SYMPTOMS_LENGTH:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"La descrizione non può superare {MAX_SYMPTOMS_LENGTH} caratteri.",
        )

    plant_photo = None
    if photo is not None and photo.filename:
        media_type = photo.content_type
        if media_type not in plant_care.ALLOWED_PHOTO_TYPES:
            # Some mobile uploaders send application/octet-stream: trust the
            # extension instead.
            media_type = mimetypes.guess_type(photo.filename)[0]
        if media_type not in plant_care.ALLOWED_PHOTO_TYPES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Formato non supportato. Carica una foto JPEG, PNG o WebP.")
        data = await photo.read()
        if not data:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "La foto caricata è vuota.")
        if len(data) > settings.max_plant_photo_size_mb * 1024 * 1024:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"La foto supera la dimensione massima di {settings.max_plant_photo_size_mb} MB.",
            )
        plant_photo = plant_care.Photo(data=data, media_type=media_type)

    if species is None and plant_photo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Seleziona una specie dall'elenco oppure carica una foto.")

    source = IdentificationSource.AI_VISION
    score = None
    species_hint = None
    if species is not None:
        source = IdentificationSource.CATALOG
        species_hint = f"{species.common_name} ({species.scientific_name})"
    else:
        match = await plant_care.identify_with_plantnet(plant_photo)
        if match is not None:
            source = IdentificationSource.PLANTNET
            score = match.score
            species_hint = (
                f"{match.common_name} ({match.scientific_name})" if match.common_name else match.scientific_name
            ) + f", riconosciuta da PlantNet con affidabilità {match.score:.0%}"

    try:
        sheet = await plant_care.generate_sheet(species_hint=species_hint, symptoms=symptoms, photo=plant_photo)
    except plant_care.PlantCareUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))

    return RecoverySheetPublic(
        **sheet,
        identification_source=source,
        identification_score=score,
        disclaimer=plant_care.DISCLAIMER,
        generated_at=datetime.now(timezone.utc),
    )
