from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.project import ProjectGuest
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.auth import UserResponse
from app.schemas.member import MemberInviteRequest, ProjectMemberResponse, WorkspaceMemberResponse
from app.services.access import get_user_or_404
from app.services.auth import get_user_by_email
from app.services.projects import get_project_or_404, user_can_access_project
from app.services.workspaces import ensure_workspace_access, ensure_workspace_owner, user_can_access_workspace


def get_invited_user(db: Session, payload: MemberInviteRequest) -> User:
    if payload.user_id is not None:
        return get_user_or_404(db, payload.user_id)

    user = get_user_by_email(db, payload.email or "")
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invited user not found")
    return user


def build_workspace_member_response(member: WorkspaceMember, user: User) -> WorkspaceMemberResponse:
    return WorkspaceMemberResponse(
        id=member.id,
        workspace_id=member.workspace_id,
        role=member.role,
        user=UserResponse.model_validate(user),
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


def list_workspace_members(db: Session, workspace_id: int, current_user_id: int) -> list[WorkspaceMemberResponse]:
    ensure_workspace_access(db, current_user_id, workspace_id)
    statement = (
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at.asc(), WorkspaceMember.id.asc())
    )
    return [build_workspace_member_response(member, user) for member, user in db.execute(statement).all()]


def create_workspace_member(
    db: Session,
    workspace_id: int,
    current_user_id: int,
    payload: MemberInviteRequest,
) -> WorkspaceMemberResponse:
    workspace = ensure_workspace_owner(db, current_user_id, workspace_id)
    invited_user = get_invited_user(db, payload)
    if invited_user.id == workspace.owner_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already the workspace owner")

    member = WorkspaceMember(workspace_id=workspace_id, user_id=invited_user.id, role=payload.role)
    db.add(member)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workspace member already exists") from exc

    db.refresh(member)
    return build_workspace_member_response(member, invited_user)


def delete_workspace_member(db: Session, member_id: int, current_user_id: int) -> None:
    member = db.get(WorkspaceMember, member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace member not found")

    workspace = ensure_workspace_owner(db, current_user_id, member.workspace_id)
    if member.user_id == workspace.owner_id or member.role == "owner":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace owner cannot be removed")

    db.delete(member)
    db.commit()


def build_project_member_response(
    *,
    project_id: int,
    membership_type: str,
    user: User,
    role: Optional[str],
    member_id: Optional[int],
    created_at,
    updated_at,
) -> ProjectMemberResponse:
    return ProjectMemberResponse(
        id=member_id,
        project_id=project_id,
        membership_type=membership_type,
        role=role,
        user=UserResponse.model_validate(user),
        created_at=created_at,
        updated_at=updated_at,
    )


def list_project_members(db: Session, project_id: int, current_user_id: int) -> list[ProjectMemberResponse]:
    get_user_or_404(db, current_user_id)
    project = get_project_or_404(db, project_id)
    if not user_can_access_project(db, current_user_id, project):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    project_members: list[ProjectMemberResponse] = []
    seen_user_ids: set[int] = set()

    workspace_statement = (
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == project.workspace_id)
        .order_by(WorkspaceMember.created_at.asc(), WorkspaceMember.id.asc())
    )
    for member, user in db.execute(workspace_statement).all():
        seen_user_ids.add(user.id)
        project_members.append(
            build_project_member_response(
                project_id=project_id,
                membership_type="workspace",
                user=user,
                role=member.role,
                member_id=None,
                created_at=member.created_at,
                updated_at=member.updated_at,
            )
        )

    guest_statement = (
        select(ProjectGuest, User)
        .join(User, User.id == ProjectGuest.user_id)
        .where(ProjectGuest.project_id == project_id)
        .order_by(ProjectGuest.created_at.asc(), ProjectGuest.id.asc())
    )
    for guest, user in db.execute(guest_statement).all():
        if user.id in seen_user_ids:
            continue
        project_members.append(
            build_project_member_response(
                project_id=project_id,
                membership_type="project_guest",
                user=user,
                role="guest",
                member_id=guest.id,
                created_at=guest.created_at,
                updated_at=guest.updated_at,
            )
        )

    return project_members


def create_project_member(
    db: Session,
    project_id: int,
    current_user_id: int,
    payload: MemberInviteRequest,
) -> ProjectMemberResponse:
    project = get_project_or_404(db, project_id)
    ensure_workspace_owner(db, current_user_id, project.workspace_id)
    invited_user = get_invited_user(db, payload)
    if user_can_access_workspace(db, invited_user.id, project.workspace_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already has project access through workspace")

    guest = ProjectGuest(project_id=project_id, user_id=invited_user.id)
    db.add(guest)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project member already exists") from exc

    db.refresh(guest)
    return build_project_member_response(
        project_id=project_id,
        membership_type="project_guest",
        user=invited_user,
        role="guest",
        member_id=guest.id,
        created_at=guest.created_at,
        updated_at=guest.updated_at,
    )


def delete_project_member(db: Session, member_id: int, current_user_id: int) -> None:
    guest = db.get(ProjectGuest, member_id)
    if guest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project member not found")

    project = get_project_or_404(db, guest.project_id)
    ensure_workspace_owner(db, current_user_id, project.workspace_id)
    db.delete(guest)
    db.commit()
