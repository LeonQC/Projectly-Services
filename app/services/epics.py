from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Epic
from app.schemas.epic import EpicCreate, EpicUpdate
from app.services.projects import ensure_project_access


def get_epic_or_404(db: Session, epic_id: int) -> Epic:
    epic = db.get(Epic, epic_id)
    if epic is None or epic.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Epic not found")
    return epic


def ensure_epic_access(db: Session, user_id: int, epic_id: int) -> Epic:
    epic = get_epic_or_404(db, epic_id)
    ensure_project_access(db, user_id, epic.project_id)
    return epic


def list_project_epics(db: Session, project_id: int, current_user_id: int) -> list[Epic]:
    ensure_project_access(db, current_user_id, project_id)
    statement = (
        select(Epic)
        .where(Epic.project_id == project_id, Epic.archived.is_(False))
        .order_by(Epic.position.asc(), Epic.deadline.asc().nulls_last(), Epic.created_at.asc(), Epic.id.asc())
    )
    return list(db.scalars(statement).all())


def create_epic(db: Session, project_id: int, current_user_id: int, payload: EpicCreate) -> Epic:
    ensure_project_access(db, current_user_id, project_id)
    epic = Epic(
        project_id=project_id,
        title=payload.title,
        deadline=payload.deadline,
        position=payload.position,
    )
    db.add(epic)
    db.commit()
    db.refresh(epic)
    return epic


def get_epic(db: Session, epic_id: int, current_user_id: int) -> Epic:
    return ensure_epic_access(db, current_user_id, epic_id)


def update_epic(db: Session, epic_id: int, current_user_id: int, payload: EpicUpdate) -> Epic:
    epic = ensure_epic_access(db, current_user_id, epic_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(epic, field, value)

    db.commit()
    db.refresh(epic)
    return epic


def archive_epic(db: Session, epic_id: int, current_user_id: int) -> None:
    epic = ensure_epic_access(db, current_user_id, epic_id)
    epic.archived = True
    db.commit()
