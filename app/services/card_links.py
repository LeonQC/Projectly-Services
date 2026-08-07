from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.models.project import Card, CardLink
from app.schemas.card_link import CardLinkCreate, CardLinkResponse, LinkedCardResponse
from app.services.activities import create_card_activity
from app.services.cards import ensure_card_access


def get_card_link_or_404(db: Session, link_id: int) -> CardLink:
    link = db.get(CardLink, link_id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card link not found")
    return link


def build_card_link_response(link: CardLink, source_card: Card, target_card: Card) -> CardLinkResponse:
    return CardLinkResponse(
        id=link.id,
        source_card_id=link.source_card_id,
        target_card_id=link.target_card_id,
        relationship=link.relationship,
        created_by_id=link.created_by_id,
        source_card=LinkedCardResponse.model_validate(source_card),
        target_card=LinkedCardResponse.model_validate(target_card),
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


def list_card_links(db: Session, card_id: int, current_user_id: int) -> list[CardLinkResponse]:
    ensure_card_access(db, current_user_id, card_id)
    source_card = aliased(Card)
    target_card = aliased(Card)
    statement = (
        select(CardLink, source_card, target_card)
        .join(source_card, source_card.id == CardLink.source_card_id)
        .join(target_card, target_card.id == CardLink.target_card_id)
        .where(
            or_(CardLink.source_card_id == card_id, CardLink.target_card_id == card_id),
            source_card.archived.is_(False),
            target_card.archived.is_(False),
        )
        .order_by(CardLink.created_at.asc(), CardLink.id.asc())
    )

    links: list[CardLinkResponse] = []
    for link, source, target in db.execute(statement).all():
        try:
            ensure_card_access(db, current_user_id, source.id)
            ensure_card_access(db, current_user_id, target.id)
        except HTTPException:
            continue
        links.append(build_card_link_response(link, source, target))
    return links


def create_card_link(
    db: Session,
    card_id: int,
    current_user_id: int,
    payload: CardLinkCreate,
) -> CardLinkResponse:
    source_card = ensure_card_access(db, current_user_id, card_id)
    target_card = ensure_card_access(db, current_user_id, payload.target_card_id)
    if source_card.id == target_card.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Card cannot link to itself")

    link = CardLink(
        source_card_id=source_card.id,
        target_card_id=target_card.id,
        relationship=payload.relationship,
        created_by_id=current_user_id,
    )
    db.add(link)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Card link already exists") from exc

    create_card_activity(
        db,
        card_id=source_card.id,
        actor_id=current_user_id,
        action="link_added",
        metadata={
            "card_link_id": link.id,
            "target_card_id": target_card.id,
            "relationship": link.relationship,
        },
    )
    db.commit()
    db.refresh(link)
    return build_card_link_response(link, source_card, target_card)


def delete_card_link(db: Session, link_id: int, current_user_id: int) -> None:
    link = get_card_link_or_404(db, link_id)
    ensure_card_access(db, current_user_id, link.source_card_id)
    ensure_card_access(db, current_user_id, link.target_card_id)
    source_card_id = link.source_card_id
    target_card_id = link.target_card_id
    relationship = link.relationship
    db.delete(link)
    create_card_activity(
        db,
        card_id=source_card_id,
        actor_id=current_user_id,
        action="link_removed",
        metadata={
            "card_link_id": link_id,
            "target_card_id": target_card_id,
            "relationship": relationship,
        },
    )
    db.commit()
