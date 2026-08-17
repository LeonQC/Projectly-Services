from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class GitHubAppInstallationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    installation_id: int
    account_login: Optional[str]
    account_type: Optional[str]
    account_id: Optional[int]
    repository_selection: Optional[str]
    setup_action: Optional[str]
    sender_login: Optional[str]
    installed_by_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class GitHubAppWebhookResponse(BaseModel):
    event: str
    delivery_id: Optional[str]
    handled: bool
