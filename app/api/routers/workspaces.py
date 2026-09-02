from fastapi import APIRouter, status

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.responses import success_response
from app.schemas.member import WorkspaceMemberResponse, WorkspaceMemberRoleUpdate
from app.schemas.project import ProjectCreate, ProjectResponse
from app.schemas.workspace import WorkspaceCreate, WorkspaceResponse, WorkspaceUpdate
from app.services import members as members_service
from app.services import projects as projects_service
from app.services import workspaces as workspaces_service


router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("")
def list_workspaces(db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    workspaces = workspaces_service.list_workspaces(db, current_user_id)
    return success_response(data=[WorkspaceResponse.model_validate(workspace) for workspace in workspaces])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_workspace(payload: WorkspaceCreate, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    workspace = workspaces_service.create_workspace(db, current_user_id, payload)
    return success_response(data=WorkspaceResponse.model_validate(workspace), message="Workspace created")


@router.get("/deleted")
def list_deleted_workspaces(db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    workspaces = workspaces_service.list_deleted_workspaces(db, current_user_id)
    return success_response(data=[WorkspaceResponse.model_validate(workspace) for workspace in workspaces])


@router.get("/{workspace_id}")
def get_workspace(workspace_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    workspace = workspaces_service.ensure_workspace_access(db, current_user_id, workspace_id)
    return success_response(data=WorkspaceResponse.model_validate(workspace))


@router.patch("/{workspace_id}")
def update_workspace(
    workspace_id: int,
    payload: WorkspaceUpdate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    workspace = workspaces_service.update_workspace(db, workspace_id, current_user_id, payload)
    return success_response(data=WorkspaceResponse.model_validate(workspace), message="Workspace updated")


@router.delete("/{workspace_id}")
def delete_workspace(workspace_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    workspaces_service.archive_workspace(db, workspace_id, current_user_id)
    return success_response(message="Workspace deleted")


@router.patch("/{workspace_id}/restore")
def restore_workspace(workspace_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    workspace = workspaces_service.restore_workspace(db, workspace_id, current_user_id)
    return success_response(data=WorkspaceResponse.model_validate(workspace), message="Workspace restored")


@router.delete("/{workspace_id}/permanent")
def permanently_delete_workspace(workspace_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    workspaces_service.permanently_delete_workspace(db, workspace_id, current_user_id)
    return success_response(message="Workspace permanently deleted")


@router.get("/{workspace_id}/members")
def list_workspace_members(workspace_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    members = members_service.list_workspace_members(db, workspace_id, current_user_id)
    return success_response(data=[WorkspaceMemberResponse.model_validate(member) for member in members])


@router.delete("/members/{member_id}")
def delete_workspace_member(member_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    members_service.delete_workspace_member(db, member_id, current_user_id)
    return success_response(message="Workspace member removed")


@router.patch("/members/{member_id}")
def update_workspace_member_role(
    member_id: int,
    payload: WorkspaceMemberRoleUpdate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    member = members_service.update_workspace_member_role(db, member_id, current_user_id, payload)
    return success_response(data=WorkspaceMemberResponse.model_validate(member), message="Workspace member role updated")


@router.get("/{workspace_id}/projects")
def list_workspace_projects(workspace_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    projects = projects_service.list_workspace_projects(db, workspace_id, current_user_id)
    return success_response(data=[ProjectResponse.model_validate(project) for project in projects])


@router.post("/{workspace_id}/projects", status_code=status.HTTP_201_CREATED)
def create_workspace_project(
    workspace_id: int,
    payload: ProjectCreate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    project = projects_service.create_project(db, workspace_id, current_user_id, payload)
    return success_response(data=ProjectResponse.model_validate(project), message="Project created")
