from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.models.notification import Invitation
from app.models.project import ProjectGuest
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.auth import UserResponse
from app.schemas.invitation import InvitationCreate, InvitationResponse
from app.services.access import get_user_or_404
from app.services.auth import get_user_by_email
from app.services.projects import get_project_or_404, user_can_access_project
from app.services.workspaces import ensure_workspace_owner, user_can_access_workspace


def get_invitee(db: Session, payload: InvitationCreate) -> User:
    if payload.user_id is not None:
        return get_user_or_404(db, payload.user_id)

    user = get_user_by_email(db, payload.email or "")
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invited user not found")
    return user


def build_invitation_response(invitation: Invitation, inviter: User, invitee: User) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.id,
        target_type=invitation.target_type,
        target_id=invitation.target_id,
        inviter_id=invitation.inviter_id,
        invitee_id=invitation.invitee_id,
        role=invitation.role,
        status=invitation.status,
        inviter=UserResponse.model_validate(inviter),
        invitee=UserResponse.model_validate(invitee),
        created_at=invitation.created_at,
        updated_at=invitation.updated_at,
    )


def create_workspace_invitation(
    db: Session,
    workspace_id: int,
    current_user_id: int,
    payload: InvitationCreate,
) -> InvitationResponse:
    workspace = ensure_workspace_owner(db, current_user_id, workspace_id)
    invitee = get_invitee(db, payload)
    if invitee.id == workspace.owner_id or user_can_access_workspace(db, invitee.id, workspace_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already has workspace access")

    invitation = Invitation(
        target_type="workspace",
        target_id=workspace_id,
        inviter_id=current_user_id,
        invitee_id=invitee.id,
        role=payload.role,
        status="pending",
    )
    db.add(invitation)
    try:
        db.flush()
        from app.services.notifications import create_invitation_notification

        create_invitation_notification(db, invitation)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invitation already exists") from exc

    db.refresh(invitation)
    inviter = get_user_or_404(db, current_user_id)
    return build_invitation_response(invitation, inviter, invitee)


def create_project_invitation(
    db: Session,
    project_id: int,
    current_user_id: int,
    payload: InvitationCreate,
) -> InvitationResponse:
    project = get_project_or_404(db, project_id)
    ensure_workspace_owner(db, current_user_id, project.workspace_id)
    invitee = get_invitee(db, payload)
    if user_can_access_project(db, invitee.id, project):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already has project access")

    invitation = Invitation(
        target_type="project",
        target_id=project_id,
        inviter_id=current_user_id,
        invitee_id=invitee.id,
        role="guest",
        status="pending",
    )
    db.add(invitation)
    try:
        db.flush()
        from app.services.notifications import create_invitation_notification

        create_invitation_notification(db, invitation)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invitation already exists") from exc

    db.refresh(invitation)
    inviter = get_user_or_404(db, current_user_id)
    return build_invitation_response(invitation, inviter, invitee)


def list_my_invitations(db: Session, current_user_id: int) -> list[InvitationResponse]:
    get_user_or_404(db, current_user_id)
    inviter_user = aliased(User)
    invitee_user = aliased(User)
    statement = (
        select(Invitation, inviter_user, invitee_user)
        .join(inviter_user, inviter_user.id == Invitation.inviter_id)
        .join(invitee_user, invitee_user.id == Invitation.invitee_id)
        .where(Invitation.invitee_id == current_user_id, Invitation.status == "pending")
        .order_by(Invitation.created_at.desc(), Invitation.id.desc())
    )
    invitations: list[InvitationResponse] = []
    for invitation, inviter, invitee in db.execute(statement).all():
        invitations.append(build_invitation_response(invitation, inviter, invitee))
    return invitations


def get_my_pending_invitation(db: Session, invitation_id: int, current_user_id: int) -> Invitation:
    invitation = db.get(Invitation, invitation_id)
    if invitation is None or invitation.invitee_id != current_user_id or invitation.status != "pending":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return invitation


def accept_invitation(db: Session, invitation_id: int, current_user_id: int) -> InvitationResponse:
    invitation = get_my_pending_invitation(db, invitation_id, current_user_id)
    if invitation.target_type == "workspace":
        member = WorkspaceMember(
            workspace_id=invitation.target_id,
            user_id=current_user_id,
            role=invitation.role,
        )
        db.add(member)
    else:
        guest = ProjectGuest(project_id=invitation.target_id, user_id=current_user_id)
        db.add(guest)

    invitation.status = "accepted"
    from app.services.notifications import mark_invitation_notification_read

    mark_invitation_notification_read(db, invitation_id, current_user_id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already has access") from exc

    db.refresh(invitation)
    inviter = get_user_or_404(db, invitation.inviter_id)
    invitee = get_user_or_404(db, invitation.invitee_id)
    return build_invitation_response(invitation, inviter, invitee)


def decline_invitation(db: Session, invitation_id: int, current_user_id: int) -> InvitationResponse:
    invitation = get_my_pending_invitation(db, invitation_id, current_user_id)
    invitation.status = "declined"
    from app.services.notifications import mark_invitation_notification_read

    mark_invitation_notification_read(db, invitation_id, current_user_id)
    db.commit()
    db.refresh(invitation)
    inviter = get_user_or_404(db, invitation.inviter_id)
    invitee = get_user_or_404(db, invitation.invitee_id)
    return build_invitation_response(invitation, inviter, invitee)
