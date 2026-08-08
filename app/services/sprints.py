from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Card, Epic, Sprint
from app.schemas.sprint import CardSprintUpdate, SprintCreate, SprintUpdate
from app.services.cards import ensure_card_access
from app.services.epics import ensure_epic_access, get_epic_or_404
from app.services.projects import ensure_project_access


def get_sprint_or_404(db: Session, sprint_id: int) -> Sprint:
    sprint = db.get(Sprint, sprint_id)
    if sprint is None or sprint.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sprint not found")
    return sprint


def ensure_sprint_access(db: Session, user_id: int, sprint_id: int) -> Sprint:
    sprint = get_sprint_or_404(db, sprint_id)
    epic = get_epic_or_404(db, sprint.epic_id)
    ensure_project_access(db, user_id, epic.project_id)
    return sprint


def list_epic_sprints(db: Session, epic_id: int, current_user_id: int) -> list[Sprint]:
    ensure_epic_access(db, current_user_id, epic_id)
    statement = (
        select(Sprint)
        .where(Sprint.epic_id == epic_id, Sprint.archived.is_(False))
        .order_by(Sprint.start_date.asc().nulls_last(), Sprint.created_at.asc(), Sprint.id.asc())
    )
    return list(db.scalars(statement).all())


def create_sprint(db: Session, epic_id: int, current_user_id: int, payload: SprintCreate) -> Sprint:
    ensure_epic_access(db, current_user_id, epic_id)
    sprint = Sprint(
        epic_id=epic_id,
        name=payload.name,
        goal=payload.goal,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=payload.status,
    )
    db.add(sprint)
    db.commit()
    db.refresh(sprint)
    return sprint


def get_sprint(db: Session, sprint_id: int, current_user_id: int) -> Sprint:
    return ensure_sprint_access(db, current_user_id, sprint_id)


def update_sprint(db: Session, sprint_id: int, current_user_id: int, payload: SprintUpdate) -> Sprint:
    sprint = ensure_sprint_access(db, current_user_id, sprint_id)
    update_data = payload.model_dump(exclude_unset=True)

    start_date = update_data.get("start_date", sprint.start_date)
    end_date = update_data.get("end_date", sprint.end_date)
    if start_date is not None and end_date is not None and end_date < start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sprint end date cannot be before start date")

    for field, value in update_data.items():
        setattr(sprint, field, value)

    db.commit()
    db.refresh(sprint)
    return sprint


def archive_sprint(db: Session, sprint_id: int, current_user_id: int) -> None:
    sprint = ensure_sprint_access(db, current_user_id, sprint_id)
    sprint.archived = True
    db.commit()


def list_sprint_cards(db: Session, sprint_id: int, current_user_id: int) -> list[Card]:
    sprint = ensure_sprint_access(db, current_user_id, sprint_id)
    statement = (
        select(Card)
        .where(Card.sprint_id == sprint.id, Card.archived.is_(False))
        .order_by(Card.status.asc(), Card.position.asc(), Card.created_at.asc(), Card.id.asc())
    )
    return list(db.scalars(statement).all())


def update_card_sprint(db: Session, card_id: int, current_user_id: int, payload: CardSprintUpdate) -> Card:
    card = ensure_card_access(db, current_user_id, card_id)
    if payload.sprint_id is None:
        card.sprint_id = None
        db.commit()
        db.refresh(card)
        return card

    sprint = ensure_sprint_access(db, current_user_id, payload.sprint_id)
    epic = db.get(Epic, sprint.epic_id)
    if epic is None or epic.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sprint not found")

    if card.epic_id != sprint.epic_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Card does not belong to sprint epic")

    card.sprint_id = sprint.id
    db.commit()
    db.refresh(card)
    return card
