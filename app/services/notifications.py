from __future__ import annotations

from datetime import datetime, timezone
import re

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, aliased

from app.models.notification import Invitation, Notification
from app.models.project import Card, CardComment, Project
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.invitation import InvitationResponse
from app.schemas.notification import CommentMentionTarget, NotificationResponse
from app.services.access import get_user_or_404
from app.services.invitations import build_invitation_response
from app.services.mentions import list_card_mention_users


MENTION_PATTERN = re.compile(r"@([A-Za-z0-9_.-]+)")


def create_invitation_notification(db: Session, invitation: Invitation) -> Notification:
    target_label = "workspace" if invitation.target_type == "workspace" else "project"
    notification = Notification(
        recipient_id=invitation.invitee_id,
        actor_id=invitation.inviter_id,
        type="invitation",
        title=f"{target_label.title()} invitation",
        body=f"You were invited to join this {target_label}.",
        source_type="invitation",
        source_id=invitation.id,
    )
    db.add(notification)
    return notification


def create_comment_mention_notifications(
    db: Session,
    *,
    card_id: int,
    comment_id: int,
    author_id: int,
    body: str,
) -> None:
    mention_names = {match.group(1).lower() for match in MENTION_PATTERN.finditer(body)}
    if not mention_names:
        return

    mentionable_users = list_card_mention_users(db, card_id, author_id)
    for user in mentionable_users:
        username_key = user.username.lower().replace(" ", "")
        if user.id == author_id or user.username.lower() not in mention_names and username_key not in mention_names:
            continue

        notification = Notification(
            recipient_id=user.id,
            actor_id=author_id,
            type="comment_mention",
            title="You were mentioned in a comment",
            body=body,
            source_type="card_comment",
            source_id=comment_id,
        )
        db.add(notification)


def delete_comment_mention_notifications(db: Session, comment_id: int) -> None:
    db.execute(
        delete(Notification).where(
            Notification.source_type == "card_comment",
            Notification.source_id == comment_id,
        )
    )


def build_notification_response(
    *,
    db: Session,
    notification: Notification,
    actor: User | None,
    invitation: Invitation | None = None,
    invitation_inviter: User | None = None,
    invitation_invitee: User | None = None,
    comment: CardComment | None = None,
    comment_card: Card | None = None,
    comment_project: Project | None = None,
) -> NotificationResponse:
    invitation_response: InvitationResponse | None = None
    if invitation is not None and invitation_inviter is not None and invitation_invitee is not None:
        invitation_response = build_invitation_response(db, invitation, invitation_inviter, invitation_invitee)

    comment_mention: CommentMentionTarget | None = None
    if comment is not None and comment_card is not None and comment_project is not None:
        comment_mention = CommentMentionTarget(
            workspace_id=comment_project.workspace_id,
            project_id=comment_card.project_id,
            card_id=comment.card_id,
            comment_id=comment.id,
        )

    return NotificationResponse(
        id=notification.id,
        recipient_id=notification.recipient_id,
        actor_id=notification.actor_id,
        type=notification.type,
        title=notification.title,
        body=notification.body,
        source_type=notification.source_type,
        source_id=notification.source_id,
        read_at=notification.read_at,
        created_at=notification.created_at,
        actor=UserResponse.model_validate(actor) if actor is not None else None,
        invitation=invitation_response,
        comment_mention=comment_mention,
    )


def list_my_notifications(db: Session, current_user_id: int) -> list[NotificationResponse]:
    get_user_or_404(db, current_user_id)
    actor_user = aliased(User)
    statement = (
        select(Notification, actor_user)
        .outerjoin(actor_user, actor_user.id == Notification.actor_id)
        .where(Notification.recipient_id == current_user_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
    )

    responses: list[NotificationResponse] = []
    for notification, actor in db.execute(statement).all():
        invitation: Invitation | None = None
        invitation_inviter: User | None = None
        invitation_invitee: User | None = None
        comment: CardComment | None = None
        comment_card: Card | None = None
        comment_project: Project | None = None

        if notification.source_type == "invitation" and notification.source_id is not None:
            invitation = db.get(Invitation, notification.source_id)
            if invitation is not None:
                invitation_inviter = db.get(User, invitation.inviter_id)
                invitation_invitee = db.get(User, invitation.invitee_id)

        if notification.source_type == "card_comment" and notification.source_id is not None:
            comment = db.get(CardComment, notification.source_id)
            if comment is None:
                continue
            if comment is not None:
                comment_card = db.get(Card, comment.card_id)
                if comment_card is not None:
                    comment_project = db.get(Project, comment_card.project_id)
            if comment_card is None or comment_project is None:
                continue

        responses.append(
            build_notification_response(
                db=db,
                notification=notification,
                actor=actor,
                invitation=invitation,
                invitation_inviter=invitation_inviter,
                invitation_invitee=invitation_invitee,
                comment=comment,
                comment_card=comment_card,
                comment_project=comment_project,
            )
        )
    return responses


def mark_notification_read(db: Session, notification_id: int, current_user_id: int) -> NotificationResponse:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.recipient_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)

    actor = db.get(User, notification.actor_id) if notification.actor_id is not None else None
    comment: CardComment | None = None
    comment_card: Card | None = None
    comment_project: Project | None = None
    if notification.source_type == "card_comment" and notification.source_id is not None:
        comment = db.get(CardComment, notification.source_id)
        if comment is not None:
            comment_card = db.get(Card, comment.card_id)
            if comment_card is not None:
                comment_project = db.get(Project, comment_card.project_id)

    return build_notification_response(
        db=db,
        notification=notification,
        actor=actor,
        comment=comment,
        comment_card=comment_card,
        comment_project=comment_project,
    )


def mark_invitation_notification_read(db: Session, invitation_id: int, current_user_id: int) -> None:
    statement = select(Notification).where(
        Notification.recipient_id == current_user_id,
        Notification.source_type == "invitation",
        Notification.source_id == invitation_id,
    )
    notification = db.scalar(statement)
    if notification is None:
        return

    notification.read_at = datetime.now(timezone.utc)
