from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.project import Card, Epic, Sprint, RagChunk
from app.schemas.epic import EpicCreate, EpicUpdate
from app.services.cards import permanently_delete_card_records
from app.services.projects import ensure_project_access
from app.services.rag_events import (
    publish_rag_source_delete,
    publish_rag_source_upsert,
)


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
    publish_rag_source_upsert("epic", epic.id)
    return epic


def get_epic(db: Session, epic_id: int, current_user_id: int) -> Epic:
    return ensure_epic_access(db, current_user_id, epic_id)


def update_epic(db: Session, epic_id: int, current_user_id: int, payload: EpicUpdate) -> Epic:
    epic = ensure_epic_access(db, current_user_id, epic_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(epic, field, value)

    sprint_ids = list(
        db.scalars(
            select(Sprint.id).where(Sprint.epic_id == epic.id)
        ).all()
    )

    db.commit()
    db.refresh(epic)

    publish_rag_source_upsert("epic", epic.id)

    if "title" in update_data:
        for sprint_id in sprint_ids:
            publish_rag_source_upsert("sprint", sprint_id)
    return epic


def archive_epic(db: Session, epic_id: int, current_user_id: int) -> None:
    epic = ensure_epic_access(db, current_user_id, epic_id)
    epic.archived = True
    db.commit()
    publish_rag_source_upsert("epic", epic.id)


def restore_epic(db: Session, epic_id: int, current_user_id: int) -> Epic:
    epic = db.get(Epic, epic_id)
    if epic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Epic not found")
    ensure_project_access(db, current_user_id, epic.project_id)
    epic.archived = False
    db.commit()
    db.refresh(epic)
    publish_rag_source_upsert("epic", epic.id)
    return epic


def permanently_delete_epic(
    db: Session,
    epic_id: int,
    current_user_id: int,
) -> None:
    epic = db.get(Epic, epic_id)
    if epic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Epic not found",
        )

    ensure_project_access(
        db,
        current_user_id,
        epic.project_id,
    )

    sprint_ids = list(
        db.scalars(
            select(Sprint.id).where(
                Sprint.epic_id == epic_id
            )
        ).all()
    )

    card_condition = Card.epic_id == epic_id
    if sprint_ids:
        card_condition = (
            card_condition
            | Card.sprint_id.in_(sprint_ids)
        )

    card_ids = list(
        db.scalars(
            select(Card.id).where(card_condition)
        ).all()
    )

    permanently_delete_card_records(db, card_ids)

    if sprint_ids:
        db.execute(
            delete(RagChunk).where(
                RagChunk.source_type == "sprint",
                RagChunk.source_id.in_(sprint_ids),
            )
        )
        db.execute(
            delete(Sprint).where(
                Sprint.id.in_(sprint_ids)
            )
        )

    db.execute(
        delete(RagChunk).where(
            RagChunk.source_type == "epic",
            RagChunk.source_id == epic_id,
        )
    )

    db.delete(epic)
    db.commit()

    for card_id in card_ids:
        publish_rag_source_delete("card", card_id)

    for sprint_id in sprint_ids:
        publish_rag_source_delete("sprint", sprint_id)

    publish_rag_source_delete("epic", epic_id)