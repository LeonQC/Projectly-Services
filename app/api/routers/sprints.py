from fastapi import APIRouter, status

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.responses import success_response
from app.schemas.sprint import CardSprintUpdate, SprintCreate, SprintResponse, SprintUpdate
from app.services import cards as cards_service
from app.services import sprints as sprints_service


router = APIRouter(tags=["sprints"])


@router.get("/epics/{epic_id}/sprints")
def list_epic_sprints(epic_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    sprints = sprints_service.list_epic_sprints(db, epic_id, current_user_id)
    return success_response(data=[SprintResponse.model_validate(sprint) for sprint in sprints])


@router.post("/epics/{epic_id}/sprints", status_code=status.HTTP_201_CREATED)
def create_epic_sprint(
    epic_id: int,
    payload: SprintCreate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    sprint = sprints_service.create_sprint(db, epic_id, current_user_id, payload)
    return success_response(data=SprintResponse.model_validate(sprint), message="Sprint created")


@router.get("/sprints/{sprint_id}")
def get_sprint(sprint_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    sprint = sprints_service.get_sprint(db, sprint_id, current_user_id)
    return success_response(data=SprintResponse.model_validate(sprint))


@router.patch("/sprints/{sprint_id}")
def update_sprint(
    sprint_id: int,
    payload: SprintUpdate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    sprint = sprints_service.update_sprint(db, sprint_id, current_user_id, payload)
    return success_response(data=SprintResponse.model_validate(sprint), message="Sprint updated")


@router.delete("/sprints/{sprint_id}")
def delete_sprint(sprint_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    sprints_service.archive_sprint(db, sprint_id, current_user_id)
    return success_response(message="Sprint deleted")


@router.patch("/sprints/{sprint_id}/restore")
def restore_sprint(sprint_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    sprint = sprints_service.restore_sprint(db, sprint_id, current_user_id)
    return success_response(data=SprintResponse.model_validate(sprint), message="Sprint restored")


@router.delete("/sprints/{sprint_id}/permanent")
def permanently_delete_sprint(sprint_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    sprints_service.permanently_delete_sprint(db, sprint_id, current_user_id)
    return success_response(message="Sprint permanently deleted")


@router.get("/sprints/{sprint_id}/cards")
def list_sprint_cards(sprint_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    cards = sprints_service.list_sprint_cards(db, sprint_id, current_user_id)
    return success_response(data=cards_service.build_card_responses(db, cards))


@router.patch("/cards/{card_id}/sprint")
def update_card_sprint(
    card_id: int,
    payload: CardSprintUpdate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    card = sprints_service.update_card_sprint(db, card_id, current_user_id, payload)
    return success_response(data=cards_service.build_card_response(db, card), message="Card sprint updated")
