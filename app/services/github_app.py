from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.project import Card, GitHubAppInstallation, GitHubEvent


CARD_REFERENCE_PATTERN = re.compile(
    r"(?:\bcard\s*[-#:]?\s*|\bprojectly\s*[-#]\s*|#card\s*[-#:]?\s*)(\d+)",
    re.IGNORECASE,
)


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


def extract_repository(payload: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    repository = payload.get("repository")
    if not isinstance(repository, dict):
        return None, None

    owner = repository.get("owner")
    repo_owner = owner.get("login") if isinstance(owner, dict) else None
    repo_name = repository.get("name")
    if isinstance(repo_owner, str) and isinstance(repo_name, str):
        return repo_owner, repo_name

    full_name = repository.get("full_name")
    if isinstance(full_name, str) and "/" in full_name:
        owner_name, repository_name = full_name.split("/", 1)
        return owner_name, repository_name

    return None, repo_name if isinstance(repo_name, str) else None


def extract_sender_login(payload: dict[str, Any]) -> Optional[str]:
    sender = payload.get("sender")
    if not isinstance(sender, dict):
        return None

    login = sender.get("login")
    return login if isinstance(login, str) else None


def extract_branch_from_ref(ref: Any) -> Optional[str]:
    if not isinstance(ref, str):
        return None
    if ref.startswith("refs/heads/"):
        return ref.removeprefix("refs/heads/")
    return ref


def extract_card_reference_ids(*values: Optional[str]) -> list[int]:
    card_ids: list[int] = []
    seen_card_ids: set[int] = set()
    for value in values:
        if not value:
            continue
        for match in CARD_REFERENCE_PATTERN.finditer(value):
            card_id = int(match.group(1))
            if card_id in seen_card_ids:
                continue
            seen_card_ids.add(card_id)
            card_ids.append(card_id)
    return card_ids


def match_card_id_for_event(db: Session, event: GitHubEvent) -> Optional[int]:
    card_ids = extract_card_reference_ids(event.title, event.message, event.branch_name)
    for card_id in card_ids:
        if db.get(Card, card_id) is not None:
            return card_id
    return None


def delivery_already_stored(db: Session, delivery_id: Optional[str]) -> bool:
    if not delivery_id:
        return False

    return db.scalar(select(GitHubEvent.id).where(GitHubEvent.delivery_id == delivery_id).limit(1)) is not None


def build_push_events(
    *,
    delivery_id: Optional[str],
    installation_id: Optional[int],
    payload: dict[str, Any],
) -> list[GitHubEvent]:
    repo_owner, repo_name = extract_repository(payload)
    sender_login = extract_sender_login(payload)
    branch_name = extract_branch_from_ref(payload.get("ref"))
    commits = payload.get("commits")
    events: list[GitHubEvent] = []

    if isinstance(commits, list) and commits:
        for commit in commits:
            if not isinstance(commit, dict):
                continue

            commit_sha = commit.get("id")
            message = commit.get("message")
            commit_url = commit.get("distinct_url") or commit.get("url")
            events.append(
                GitHubEvent(
                    delivery_id=delivery_id,
                    installation_id=installation_id,
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    event_type="push",
                    branch_name=branch_name,
                    commit_sha=commit_sha if isinstance(commit_sha, str) else None,
                    title="Commit pushed",
                    message=message if isinstance(message, str) else None,
                    url=commit_url if isinstance(commit_url, str) else None,
                    sender_login=sender_login,
                    raw_payload={"commit": commit, "repository": payload.get("repository")},
                )
            )
        return events

    head_commit = payload.get("head_commit")
    message = head_commit.get("message") if isinstance(head_commit, dict) else None
    events.append(
        GitHubEvent(
            delivery_id=delivery_id,
            installation_id=installation_id,
            repo_owner=repo_owner,
            repo_name=repo_name,
            event_type="push",
            branch_name=branch_name,
            commit_sha=payload.get("after") if isinstance(payload.get("after"), str) else None,
            title="Push received",
            message=message if isinstance(message, str) else None,
            url=payload.get("compare") if isinstance(payload.get("compare"), str) else None,
            sender_login=sender_login,
            raw_payload=payload,
        )
    )
    return events


def build_pull_request_event(
    *,
    delivery_id: Optional[str],
    installation_id: Optional[int],
    payload: dict[str, Any],
) -> list[GitHubEvent]:
    pull_request = payload.get("pull_request")
    if not isinstance(pull_request, dict):
        return []

    repo_owner, repo_name = extract_repository(payload)
    sender_login = extract_sender_login(payload)
    action = payload.get("action")
    head = pull_request.get("head")
    branch_name = head.get("ref") if isinstance(head, dict) else None
    commit_sha = head.get("sha") if isinstance(head, dict) else None
    pull_request_number = pull_request.get("number")

    return [
        GitHubEvent(
            delivery_id=delivery_id,
            installation_id=installation_id,
            repo_owner=repo_owner,
            repo_name=repo_name,
            event_type="pull_request",
            action=action if isinstance(action, str) else None,
            branch_name=branch_name if isinstance(branch_name, str) else None,
            pull_request_number=pull_request_number if isinstance(pull_request_number, int) else None,
            commit_sha=commit_sha if isinstance(commit_sha, str) else None,
            title=pull_request.get("title") if isinstance(pull_request.get("title"), str) else None,
            message=pull_request.get("body") if isinstance(pull_request.get("body"), str) else None,
            url=pull_request.get("html_url") if isinstance(pull_request.get("html_url"), str) else None,
            sender_login=sender_login,
            raw_payload=payload,
        )
    ]


def store_github_events(
    db: Session,
    *,
    event: str,
    delivery_id: Optional[str],
    payload: dict[str, Any],
) -> list[GitHubEvent]:
    if delivery_already_stored(db, delivery_id):
        return []

    installation_id = extract_installation_id(payload)
    if event == "push":
        events = build_push_events(delivery_id=delivery_id, installation_id=installation_id, payload=payload)
    elif event == "pull_request":
        events = build_pull_request_event(delivery_id=delivery_id, installation_id=installation_id, payload=payload)
    else:
        return []

    if events:
        for github_event in events:
            github_event.card_id = match_card_id_for_event(db, github_event)
        db.add_all(events)
        db.commit()

    return events


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


def disconnect_installation(db: Session, installation_id: int, current_user_id: int) -> None:
    installation = get_installation_or_404(db, installation_id)
    if installation.installed_by_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GitHub App installation not found")

    installation.installed_by_id = None
    db.commit()


def handle_github_app_webhook(
    db: Session,
    *,
    event: str,
    delivery_id: Optional[str],
    payload: dict[str, Any],
) -> bool:
    if event not in {"ping", "installation", "installation_repositories", "push", "pull_request"}:
        return False

    installation_id = extract_installation_id(payload)
    if installation_id is not None:
        upsert_github_app_installation(db, installation_id, payload=payload)

    if event in {"push", "pull_request"}:
        store_github_events(db, event=event, delivery_id=delivery_id, payload=payload)

    if installation_id is None:
        return True
    return True
