from __future__ import annotations

import hashlib
import hmac
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.project import GitHubAppInstallation


def verify_github_webhook_signature(raw_body: bytes, signature_header: Optional[str]) -> None:
    if not settings.github_app_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub App webhook secret is not configured",
        )

    if not signature_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="GitHub signature is required")

    expected_signature = "sha256=" + hmac.new(
        settings.github_app_webhook_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature_header):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid GitHub signature")


def get_installation_or_404(db: Session, installation_id: int) -> GitHubAppInstallation:
    installation = db.scalar(
        select(GitHubAppInstallation).where(GitHubAppInstallation.installation_id == installation_id)
    )
    if installation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GitHub App installation not found")
    return installation


def extract_installation_id(payload: dict[str, Any]) -> Optional[int]:
    installation = payload.get("installation")
    if not isinstance(installation, dict):
        return None

    installation_id = installation.get("id")
    return installation_id if isinstance(installation_id, int) else None


def upsert_github_app_installation(
    db: Session,
    installation_id: int,
    *,
    payload: Optional[dict[str, Any]] = None,
    setup_action: Optional[str] = None,
    installed_by_id: Optional[int] = None,
) -> GitHubAppInstallation:
    installation = db.scalar(
        select(GitHubAppInstallation).where(GitHubAppInstallation.installation_id == installation_id)
    )
    if installation is None:
        installation = GitHubAppInstallation(installation_id=installation_id)
        db.add(installation)

    if payload:
        github_installation = payload.get("installation")
        if isinstance(github_installation, dict):
            account = github_installation.get("account")
            if isinstance(account, dict):
                installation.account_login = account.get("login")
                installation.account_type = account.get("type")
                account_id = account.get("id")
                installation.account_id = account_id if isinstance(account_id, int) else None

            repository_selection = github_installation.get("repository_selection")
            installation.repository_selection = (
                repository_selection if isinstance(repository_selection, str) else installation.repository_selection
            )

        sender = payload.get("sender")
        if isinstance(sender, dict):
            installation.sender_login = sender.get("login")

        payload_action = payload.get("action")
        if isinstance(payload_action, str):
            installation.setup_action = payload_action

        installation.raw_payload = payload

    if setup_action:
        installation.setup_action = setup_action

    if installed_by_id is not None:
        installation.installed_by_id = installed_by_id

    db.commit()
    db.refresh(installation)
    return installation


def create_callback_installation(
    db: Session,
    installation_id: int,
    setup_action: Optional[str],
) -> GitHubAppInstallation:
    return upsert_github_app_installation(db, installation_id, setup_action=setup_action)


def claim_installation(db: Session, installation_id: int, current_user_id: int) -> GitHubAppInstallation:
    return upsert_github_app_installation(db, installation_id, installed_by_id=current_user_id)


def list_user_installations(db: Session, current_user_id: int) -> list[GitHubAppInstallation]:
    statement = (
        select(GitHubAppInstallation)
        .where(GitHubAppInstallation.installed_by_id == current_user_id)
        .order_by(GitHubAppInstallation.updated_at.desc(), GitHubAppInstallation.id.desc())
    )
    return list(db.scalars(statement).all())


def handle_github_app_webhook(
    db: Session,
    *,
    event: str,
    payload: dict[str, Any],
) -> bool:
    if event not in {"ping", "installation", "installation_repositories"}:
        return False

    installation_id = extract_installation_id(payload)
    if installation_id is None:
        return True

    upsert_github_app_installation(db, installation_id, payload=payload)
    return True
