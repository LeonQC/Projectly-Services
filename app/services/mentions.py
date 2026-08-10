from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Card, ProjectGuest
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.auth import UserResponse
from app.services.cards import ensure_card_access
from app.services.projects import ensure_project_access, get_project_or_404
from app.services.workspaces import ensure_workspace_access


def list_workspace_mention_users(db: Session, workspace_id: int, current_user_id: int) -> list[UserResponse]:
    ensure_workspace_access(db, current_user_id, workspace_id)
    statement = (
        select(User)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == workspace_id, User.is_active.is_(True))
        .order_by(User.username.asc(), User.id.asc())
    )
    return [UserResponse.model_validate(user) for user in db.scalars(statement).all()]


def list_project_mention_users(db: Session, project_id: int, current_user_id: int) -> list[UserResponse]:
    project = ensure_project_access(db, current_user_id, project_id)
    users_by_id: dict[int, User] = {}

    workspace_statement = (
        select(User)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == project.workspace_id, User.is_active.is_(True))
    )
    for user in db.scalars(workspace_statement).all():
        users_by_id[user.id] = user

    guest_statement = (
        select(User)
        .join(ProjectGuest, ProjectGuest.user_id == User.id)
        .where(ProjectGuest.project_id == project_id, User.is_active.is_(True))
    )
    for user in db.scalars(guest_statement).all():
        users_by_id[user.id] = user

    return [
        UserResponse.model_validate(user)
        for user in sorted(users_by_id.values(), key=lambda user: (user.username.lower(), user.id))
    ]


def list_card_mention_users(db: Session, card_id: int, current_user_id: int) -> list[UserResponse]:
    card = ensure_card_access(db, current_user_id, card_id)
    get_project_or_404(db, card.project_id)
    return list_project_mention_users(db, card.project_id, current_user_id)
