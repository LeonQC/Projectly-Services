from fastapi import APIRouter, status

from app.api.deps import AuthenticatedUserId, CurrentUserId, DbSession
from app.core.responses import success_response
from app.schemas.auth import UserResponse
from app.schemas.invitation import InvitationCreate, InvitationResponse
from app.schemas.notification import NotificationResponse
from app.services import invitations as invitations_service
from app.services import mentions as mentions_service
from app.services import notifications as notifications_service


router = APIRouter(tags=["notifications"])


@router.get("/notifications")
def list_my_notifications(db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    notifications = notifications_service.list_my_notifications(db, current_user_id)
    return success_response(data=[NotificationResponse.model_validate(notification) for notification in notifications])


@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    notification = notifications_service.mark_notification_read(db, notification_id, current_user_id)
    return success_response(data=NotificationResponse.model_validate(notification), message="Notification read")


@router.post("/workspaces/{workspace_id}/invitations", status_code=status.HTTP_201_CREATED)
def create_workspace_invitation(
    workspace_id: int,
    payload: InvitationCreate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    invitation = invitations_service.create_workspace_invitation(db, workspace_id, current_user_id, payload)
    return success_response(data=InvitationResponse.model_validate(invitation), message="Workspace invitation created")


@router.post("/projects/{project_id}/invitations", status_code=status.HTTP_201_CREATED)
def create_project_invitation(
    project_id: int,
    payload: InvitationCreate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    invitation = invitations_service.create_project_invitation(db, project_id, current_user_id, payload)
    return success_response(data=InvitationResponse.model_validate(invitation), message="Project invitation created")


@router.get("/invitations")
def list_my_invitations(db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    invitations = invitations_service.list_my_invitations(db, current_user_id)
    return success_response(data=[InvitationResponse.model_validate(invitation) for invitation in invitations])


@router.patch("/invitations/{invitation_id}/accept")
def accept_invitation(invitation_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    invitation = invitations_service.accept_invitation(db, invitation_id, current_user_id)
    return success_response(data=InvitationResponse.model_validate(invitation), message="Invitation accepted")


@router.patch("/invitations/{invitation_id}/decline")
def decline_invitation(invitation_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    invitation = invitations_service.decline_invitation(db, invitation_id, current_user_id)
    return success_response(data=InvitationResponse.model_validate(invitation), message="Invitation declined")


@router.get("/cards/{card_id}/comments/mention-users")
def list_comment_mention_users(card_id: int, db: DbSession, current_user_id: CurrentUserId) -> dict:
    users = mentions_service.list_card_mention_users(db, card_id, current_user_id)
    return success_response(data=[UserResponse.model_validate(user) for user in users])
