from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.project import (
    Card,
    CardActivity,
    CardAttachment,
    CardComment,
    CardLabel,
    CardLink,
    CardMember,
    Epic,
    Project,
    Sprint,
)
from app.models.workspace import Workspace
from app.schemas.card import (
    CardCreate,
    CardDetailResponse,
    CardMove,
    CardResponse,
    CardUpdate,
)
from app.services.activities import create_card_activity
from app.services.projects import ensure_project_access
from app.services.search import delete_card_from_index, index_card, reindex_card_search_documents


def build_card_display_id(db: Session, card: Card) -> str:
    statement = (
        select(Workspace.name, Project.name)
        .join(Project, Project.workspace_id == Workspace.id)
        .where(Project.id == card.project_id)
    )
    result = db.execute(statement).one_or_none()

    if result is None:
        return card.title

    workspace_name, project_name = result
    return f"{workspace_name}/{project_name}/{card.title}"


def build_card_response(db: Session, card: Card) -> CardResponse:
    return CardResponse.model_validate(card).model_copy(
        update={
            "display_id": build_card_display_id(db, card),
        }
    )


def build_card_responses(
    db: Session,
    cards: list[Card],
) -> list[CardResponse]:
    return [
        build_card_response(db, card)
        for card in cards
    ]


def get_card_or_404(
    db: Session,
    card_id: int,
) -> Card:
    card = db.get(Card, card_id)

    if card is None or card.archived:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    return card


def ensure_card_access(
    db: Session,
    user_id: int,
    card_id: int,
) -> Card:
    card = get_card_or_404(db, card_id)

    ensure_project_access(
        db,
        user_id,
        card.project_id,
    )

    return card


def ensure_epic_belongs_to_project(
    db: Session,
    epic_id: int,
    project_id: int,
) -> None:
    epic = db.get(Epic, epic_id)

    if (
        epic is None
        or epic.archived
        or epic.project_id != project_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Epic does not belong to project",
        )


def list_project_cards(
    db: Session,
    project_id: int,
    current_user_id: int,
) -> list[Card]:
    ensure_project_access(
        db,
        current_user_id,
        project_id,
    )

    statement = (
        select(Card)
        .where(
            Card.project_id == project_id,
            Card.archived.is_(False),
        )
        .order_by(
            Card.status.asc(),
            Card.position.asc(),
            Card.created_at.asc(),
            Card.id.asc(),
        )
    )

    return list(
        db.scalars(statement).all()
    )


def list_archived_project_cards(
    db: Session,
    project_id: int,
    current_user_id: int,
) -> list[Card]:
    ensure_project_access(
        db,
        current_user_id,
        project_id,
    )

    statement = (
        select(Card)
        .where(
            Card.project_id == project_id,
            Card.archived.is_(True),
        )
        .order_by(
            Card.updated_at.desc(),
            Card.created_at.desc(),
            Card.id.desc(),
        )
    )

    return list(
        db.scalars(statement).all()
    )


def create_card(
    db: Session,
    project_id: int,
    current_user_id: int,
    payload: CardCreate,
) -> Card:
    ensure_project_access(
        db,
        current_user_id,
        project_id,
    )

    if payload.epic_id is not None:
        ensure_epic_belongs_to_project(
            db,
            payload.epic_id,
            project_id,
        )

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
        metadata={
            "project_id": project_id,
        },
    )

    db.commit()
    db.refresh(card)

    index_card(
        db,
        card,
    )

    return card


def get_card(
    db: Session,
    card_id: int,
    current_user_id: int,
) -> Card:
    return ensure_card_access(
        db,
        current_user_id,
        card_id,
    )


def update_card(
    db: Session,
    card_id: int,
    current_user_id: int,
    payload: CardUpdate,
) -> Card:
    card = ensure_card_access(
        db,
        current_user_id,
        card_id,
    )

    update_data = payload.model_dump(
        exclude_unset=True,
    )

    if (
        "epic_id" in update_data
        and update_data["epic_id"] is not None
    ):
        ensure_epic_belongs_to_project(
            db,
            update_data["epic_id"],
            card.project_id,
        )

    changed_fields: list[str] = []

    for field, value in update_data.items():
        if getattr(card, field) != value:
            setattr(
                card,
                field,
                value,
            )
            changed_fields.append(field)

    if changed_fields:
        metadata: dict[str, Any] = {
            "fields": changed_fields,
        }

        create_card_activity(
            db,
            card_id=card.id,
            actor_id=current_user_id,
            action="card_updated",
            metadata=metadata,
        )

    db.commit()
    db.refresh(card)

    if changed_fields:
        reindex_card_search_documents(db, card.id)

    return card


def move_card(
    db: Session,
    card_id: int,
    current_user_id: int,
    payload: CardMove,
) -> Card:
    card = ensure_card_access(
        db,
        current_user_id,
        card_id,
    )

    update_data = payload.model_dump(
        exclude_unset=True,
    )

    if (
        "sprint_id" in update_data
        and update_data["sprint_id"] is not None
    ):
        sprint = db.get(
            Sprint,
            update_data["sprint_id"],
        )

        if sprint is None or sprint.archived:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sprint not found",
            )

        if card.epic_id != sprint.epic_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Card does not belong to sprint epic",
            )

    changed_fields: list[str] = []

    for field, value in update_data.items():
        if getattr(card, field) != value:
            setattr(
                card,
                field,
                value,
            )
            changed_fields.append(field)

    if changed_fields:
        create_card_activity(
            db,
            card_id=card.id,
            actor_id=current_user_id,
            action="card_moved",
            metadata={
                "fields": changed_fields,
            },
        )

    db.commit()
    db.refresh(card)

    if changed_fields:
        index_card(
            db,
            card,
        )

    return card


def get_card_detail(
    db: Session,
    card_id: int,
    current_user_id: int,
) -> CardDetailResponse:
    from app.services import (
        attachments,
        card_labels,
        card_links,
        card_members,
        comments,
    )

    card = get_card(
        db,
        card_id,
        current_user_id,
    )

    return CardDetailResponse(
        card=build_card_response(
            db,
            card,
        ),
        labels=card_labels.list_card_labels(
            db,
            card_id,
            current_user_id,
        ),
        members=card_members.list_card_members(
            db,
            card_id,
            current_user_id,
        ),
        attachments=attachments.list_card_attachments(
            db,
            card_id,
            current_user_id,
        ),
        comments=comments.list_card_comments(
            db,
            card_id,
            current_user_id,
        ),
        links=card_links.list_card_links(
            db,
            card_id,
            current_user_id,
        ),
    )


def archive_card(
    db: Session,
    card_id: int,
    current_user_id: int,
) -> None:
    card = ensure_card_access(
        db,
        current_user_id,
        card_id,
    )

    card.archived = True

    create_card_activity(
        db,
        card_id=card.id,
        actor_id=current_user_id,
        action="card_deleted",
        metadata={
            "project_id": card.project_id,
        },
    )

    db.commit()
    db.refresh(card)

    reindex_card_search_documents(db, card.id)


def restore_card(
    db: Session,
    card_id: int,
    current_user_id: int,
) -> Card:
    card = db.get(
        Card,
        card_id,
    )

    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    ensure_project_access(
        db,
        current_user_id,
        card.project_id,
    )

    card.archived = False

    create_card_activity(
        db,
        card_id=card.id,
        actor_id=current_user_id,
        action="card_restored",
        metadata={
            "project_id": card.project_id,
        },
    )

    db.commit()
    db.refresh(card)

    reindex_card_search_documents(db, card.id)

    return card


def permanently_delete_card_records(
    db: Session,
    card_ids: list[int],
) -> None:
    if not card_ids:
        return

    db.execute(
        delete(CardAttachment).where(
            CardAttachment.card_id.in_(card_ids)
        )
    )

    db.execute(
        delete(CardComment).where(
            CardComment.card_id.in_(card_ids)
        )
    )

    db.execute(
        delete(CardLabel).where(
            CardLabel.card_id.in_(card_ids)
        )
    )

    db.execute(
        delete(CardMember).where(
            CardMember.card_id.in_(card_ids)
        )
    )

    db.execute(
        delete(CardLink).where(
            (
                CardLink.source_card_id.in_(card_ids)
            )
            |
            (
                CardLink.target_card_id.in_(card_ids)
            )
        )
    )

    db.execute(
        delete(CardActivity).where(
            CardActivity.card_id.in_(card_ids)
        )
    )

    db.execute(
        delete(Card).where(
            Card.id.in_(card_ids)
        )
    )


def permanently_delete_card(
    db: Session,
    card_id: int,
    current_user_id: int,
) -> None:
    card = db.get(
        Card,
        card_id,
    )

    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    ensure_project_access(
        db,
        current_user_id,
        card.project_id,
    )

    permanently_delete_card_records(
        db,
        [card_id],
    )

    db.commit()

    delete_card_from_index(
        card_id,
    )
