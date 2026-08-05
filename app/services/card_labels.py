from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.project import CardLabel
from app.schemas.card_label import CardLabelCreate, CardLabelUpdate
from app.services.activities import create_card_activity
from app.services.cards import ensure_card_access


def get_card_label_or_404(db: Session, label_id: int) -> CardLabel:
    label = db.get(CardLabel, label_id)
    if label is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card label not found")
    return label


def ensure_card_label_access(db: Session, user_id: int, label_id: int) -> CardLabel:
    label = get_card_label_or_404(db, label_id)
    ensure_card_access(db, user_id, label.card_id)
    return label


def list_card_labels(db: Session, card_id: int, current_user_id: int) -> list[CardLabel]:
    ensure_card_access(db, current_user_id, card_id)
    statement = (
        select(CardLabel)
        .where(CardLabel.card_id == card_id)
        .order_by(CardLabel.created_at.asc(), CardLabel.id.asc())
    )
    return list(db.scalars(statement).all())


def create_card_label(
    db: Session,
    card_id: int,
    current_user_id: int,
    payload: CardLabelCreate,
) -> CardLabel:
    ensure_card_access(db, current_user_id, card_id)
    label = CardLabel(
        card_id=card_id,
        name=payload.name,
        color=payload.color,
        created_by_id=current_user_id,
    )
    db.add(label)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Card label already exists") from exc

    create_card_activity(
        db,
        card_id=card_id,
        actor_id=current_user_id,
        action="label_added",
        metadata={"label_id": label.id, "name": label.name, "color": label.color},
    )
    db.commit()
    db.refresh(label)
    return label


def update_card_label(
    db: Session,
    label_id: int,
    current_user_id: int,
    payload: CardLabelUpdate,
) -> CardLabel:
    label = ensure_card_label_access(db, current_user_id, label_id)
    update_data = payload.model_dump(exclude_unset=True)
    changed_fields: list[str] = []
    for field, value in update_data.items():
        if getattr(label, field) != value:
            setattr(label, field, value)
            changed_fields.append(field)

    if changed_fields:
        create_card_activity(
            db,
            card_id=label.card_id,
            actor_id=current_user_id,
            action="label_updated",
            metadata={"label_id": label.id, "fields": changed_fields},
        )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Card label already exists") from exc

    db.refresh(label)
    return label


def delete_card_label(db: Session, label_id: int, current_user_id: int) -> None:
    label = ensure_card_label_access(db, current_user_id, label_id)
    card_id = label.card_id
    label_name = label.name
    db.delete(label)
    create_card_activity(
        db,
        card_id=card_id,
        actor_id=current_user_id,
        action="label_deleted",
        metadata={"label_id": label_id, "name": label_name},
    )
    db.commit()
