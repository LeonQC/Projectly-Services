from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Card, Epic
from app.schemas.card import CardCreate, CardUpdate
from app.services.activities import create_card_activity
from app.services.projects import ensure_project_access


def get_card_or_404(db: Session, card_id: int) -> Card:
    card = db.get(Card, card_id)
    if card is None or card.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    return card


def ensure_card_access(db: Session, user_id: int, card_id: int) -> Card:
    card = get_card_or_404(db, card_id)
    ensure_project_access(db, user_id, card.project_id)
    return card


def ensure_epic_belongs_to_project(db: Session, epic_id: int, project_id: int) -> None:
    epic = db.get(Epic, epic_id)
    if epic is None or epic.archived or epic.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Epic does not belong to project")


def list_project_cards(db: Session, project_id: int, current_user_id: int) -> list[Card]:
    ensure_project_access(db, current_user_id, project_id)
    statement = (
        select(Card)
        .where(Card.project_id == project_id, Card.archived.is_(False))
        .order_by(Card.status.asc(), Card.position.asc(), Card.created_at.asc(), Card.id.asc())
    )
    return list(db.scalars(statement).all())


def create_card(db: Session, project_id: int, current_user_id: int, payload: CardCreate) -> Card:
    ensure_project_access(db, current_user_id, project_id)
    if payload.epic_id is not None:
        ensure_epic_belongs_to_project(db, payload.epic_id, project_id)

    card = Card(
        project_id=project_id,
        epic_id=payload.epic_id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        position=payload.position,
    )
    db.add(card)
    db.flush()
    create_card_activity(
        db,
        card_id=card.id,
        actor_id=current_user_id,
        action="card_created",
        metadata={"project_id": project_id},
    )
    db.commit()
    db.refresh(card)
    return card


def get_card(db: Session, card_id: int, current_user_id: int) -> Card:
    return ensure_card_access(db, current_user_id, card_id)


def update_card(db: Session, card_id: int, current_user_id: int, payload: CardUpdate) -> Card:
    card = ensure_card_access(db, current_user_id, card_id)
    update_data = payload.model_dump(exclude_unset=True)

    if "epic_id" in update_data and update_data["epic_id"] is not None:
        ensure_epic_belongs_to_project(db, update_data["epic_id"], card.project_id)

    changed_fields: list[str] = []
    for field, value in update_data.items():
        if getattr(card, field) != value:
            setattr(card, field, value)
            changed_fields.append(field)

    if changed_fields:
        metadata: dict[str, Any] = {"fields": changed_fields}
        create_card_activity(
            db,
            card_id=card.id,
            actor_id=current_user_id,
            action="card_updated",
            metadata=metadata,
        )

    db.commit()
    db.refresh(card)
    return card


def archive_card(db: Session, card_id: int, current_user_id: int) -> None:
    card = ensure_card_access(db, current_user_id, card_id)
    card.archived = True
    create_card_activity(
        db,
        card_id=card.id,
        actor_id=current_user_id,
        action="card_deleted",
        metadata={"project_id": card.project_id},
    )
    db.commit()
