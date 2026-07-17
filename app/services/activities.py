from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.project import CardActivity


def create_card_activity(
    db: Session,
    *,
    card_id: int,
    actor_id: Optional[int],
    action: str,
    metadata: Optional[dict[str, Any]] = None,
) -> CardActivity:
    activity = CardActivity(
        card_id=card_id,
        actor_id=actor_id,
        action=action,
        activity_metadata=metadata,
    )
    db.add(activity)
    db.flush()
    return activity
