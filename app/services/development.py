from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.project import CardGitHubLink
from app.models.project import Card
from app.schemas.development import (
    CardDevelopmentResponse,
    CardGitHubLinkCreate,
    CardGitHubLinkResponse,
    CardGitHubLinkUpdate,
    DevelopmentStatusResponse,
    GitHubBranchResponse,
    GitHubCommitResponse,
    GitHubPullRequestResponse,
    ProjectCardDevelopmentResponse,
    ProjectDevelopmentResponse,
)
from app.schemas.card import CardResponse
from app.services.activities import create_card_activity
from app.services.cards import ensure_card_access
from app.services.projects import ensure_project_access


def build_github_api_url(*path_parts: str, query: dict[str, str | int] | None = None) -> str:
    encoded_path = "/".join(quote(str(part).strip(), safe="") for part in path_parts)
    url = f"https://api.github.com/{encoded_path}"
    if query:
        return f"{url}?{urlencode(query)}"
    return url


def fetch_github_json(url: str) -> Any | None:
    request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "Projectly"})

    try:
        with urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return None
        return None
    except (UnicodeEncodeError, URLError, TimeoutError, json.JSONDecodeError):
        return None


def get_github_link_or_404(db: Session, github_link_id: int) -> CardGitHubLink:
    github_link = db.get(CardGitHubLink, github_link_id)
    if github_link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GitHub link not found")
    return github_link


def ensure_github_link_access(db: Session, current_user_id: int, github_link_id: int) -> CardGitHubLink:
    github_link = get_github_link_or_404(db, github_link_id)
    ensure_card_access(db, current_user_id, github_link.card_id)
    return github_link


def list_card_github_links(db: Session, card_id: int, current_user_id: int) -> list[CardGitHubLink]:
    ensure_card_access(db, current_user_id, card_id)
    statement = (
        select(CardGitHubLink)
        .where(CardGitHubLink.card_id == card_id)
        .order_by(CardGitHubLink.created_at.asc(), CardGitHubLink.id.asc())
    )
    return list(db.scalars(statement).all())


def create_card_github_link(
    db: Session,
    card_id: int,
    current_user_id: int,
    payload: CardGitHubLinkCreate,
) -> CardGitHubLink:
    ensure_card_access(db, current_user_id, card_id)
    github_link = CardGitHubLink(
        card_id=card_id,
        repo_owner=payload.repo_owner,
        repo_name=payload.repo_name,
        branch_name=payload.branch_name,
        pull_request_number=payload.pull_request_number,
        commit_sha=payload.commit_sha,
        url=payload.url,
        created_by_id=current_user_id,
    )
    db.add(github_link)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="GitHub link already exists") from exc

    create_card_activity(
        db,
        card_id=card_id,
        actor_id=current_user_id,
        action="github_link_added",
        metadata={
            "github_link_id": github_link.id,
            "repo": f"{github_link.repo_owner}/{github_link.repo_name}",
            "branch_name": github_link.branch_name,
            "pull_request_number": github_link.pull_request_number,
            "commit_sha": github_link.commit_sha,
        },
    )
    db.commit()
    db.refresh(github_link)
    return github_link


def update_card_github_link(
    db: Session,
    github_link_id: int,
    current_user_id: int,
    payload: CardGitHubLinkUpdate,
) -> CardGitHubLink:
    github_link = ensure_github_link_access(db, current_user_id, github_link_id)
    update_data = payload.model_dump(exclude_unset=True)
    changed_fields: list[str] = []
    for field, value in update_data.items():
        if getattr(github_link, field) != value:
            setattr(github_link, field, value)
            changed_fields.append(field)

    if changed_fields:
        create_card_activity(
            db,
            card_id=github_link.card_id,
            actor_id=current_user_id,
            action="github_link_updated",
            metadata={"github_link_id": github_link.id, "fields": changed_fields},
        )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="GitHub link already exists") from exc

    db.refresh(github_link)
    return github_link


def build_commit_response(
    *,
    github_link: CardGitHubLink,
    commit_item: dict,
    branch_name: str | None,
) -> GitHubCommitResponse:
    commit = commit_item.get("commit", {})
    author = commit.get("author") or {}
    return GitHubCommitResponse(
        sha=commit_item.get("sha", ""),
        message=commit.get("message", ""),
        author_name=author.get("name"),
        author_email=author.get("email"),
        committed_at=author.get("date"),
        url=commit_item.get("html_url", ""),
        repo_owner=github_link.repo_owner,
        repo_name=github_link.repo_name,
        branch_name=branch_name,
    )


def fetch_recent_commits_for_link(github_link: CardGitHubLink) -> list[GitHubCommitResponse]:
    if not github_link.branch_name:
        return []

    url = build_github_api_url(
        "repos",
        github_link.repo_owner,
        github_link.repo_name,
        "commits",
        query={"sha": github_link.branch_name, "per_page": 5},
    )
    commits = fetch_github_json(url)
    if not isinstance(commits, list):
        return []

    recent_commits: list[GitHubCommitResponse] = []
    for commit_item in commits:
        recent_commits.append(build_commit_response(github_link=github_link, commit_item=commit_item, branch_name=github_link.branch_name))
    return recent_commits


def fetch_linked_commit_for_link(github_link: CardGitHubLink) -> GitHubCommitResponse | None:
    if not github_link.commit_sha:
        return None

    commit_item = fetch_github_json(
        build_github_api_url(
            "repos",
            github_link.repo_owner,
            github_link.repo_name,
            "commits",
            github_link.commit_sha,
        )
    )
    if not isinstance(commit_item, dict):
        return None

    return build_commit_response(github_link=github_link, commit_item=commit_item, branch_name=github_link.branch_name)


def fetch_branch_for_link(github_link: CardGitHubLink) -> GitHubBranchResponse | None:
    if not github_link.branch_name:
        return None

    branch = fetch_github_json(
        build_github_api_url(
            "repos",
            github_link.repo_owner,
            github_link.repo_name,
            "branches",
            github_link.branch_name,
        )
    )
    if not isinstance(branch, dict):
        return None

    commit = branch.get("commit") or {}
    return GitHubBranchResponse(
        name=branch.get("name", github_link.branch_name),
        latest_commit_sha=commit.get("sha", ""),
        latest_commit_url=commit.get("html_url", ""),
        repo_owner=github_link.repo_owner,
        repo_name=github_link.repo_name,
    )


def fetch_pull_request_for_link(github_link: CardGitHubLink) -> GitHubPullRequestResponse | None:
    if github_link.pull_request_number is None:
        return None

    pull_request = fetch_github_json(
        build_github_api_url(
            "repos",
            github_link.repo_owner,
            github_link.repo_name,
            "pulls",
            str(github_link.pull_request_number),
        )
    )
    if not isinstance(pull_request, dict):
        return None

    author = pull_request.get("user") or {}
    return GitHubPullRequestResponse(
        number=pull_request.get("number", github_link.pull_request_number),
        title=pull_request.get("title", ""),
        state=pull_request.get("state", ""),
        merged=bool(pull_request.get("merged")),
        url=pull_request.get("html_url", github_link.url or ""),
        author=author.get("login"),
        created_at=pull_request.get("created_at"),
        updated_at=pull_request.get("updated_at"),
        repo_owner=github_link.repo_owner,
        repo_name=github_link.repo_name,
    )


def get_card_development(db: Session, card_id: int, current_user_id: int) -> CardDevelopmentResponse:
    github_links = list_card_github_links(db, card_id, current_user_id)
    recent_commits: list[GitHubCommitResponse] = []
    linked_commits: list[GitHubCommitResponse] = []
    branches: list[GitHubBranchResponse] = []
    pull_requests: list[GitHubPullRequestResponse] = []
    seen_commit_keys: set[tuple[str, str, str]] = set()
    seen_linked_commit_keys: set[tuple[str, str, str]] = set()
    seen_branch_keys: set[tuple[str, str, str]] = set()
    seen_pull_request_keys: set[tuple[str, str, int]] = set()

    for github_link in github_links:
        for commit in fetch_recent_commits_for_link(github_link):
            commit_key = (commit.repo_owner, commit.repo_name, commit.sha)
            if commit_key in seen_commit_keys:
                continue
            seen_commit_keys.add(commit_key)
            recent_commits.append(commit)

        linked_commit = fetch_linked_commit_for_link(github_link)
        if linked_commit is not None:
            linked_commit_key = (linked_commit.repo_owner, linked_commit.repo_name, linked_commit.sha)
            if linked_commit_key not in seen_linked_commit_keys:
                seen_linked_commit_keys.add(linked_commit_key)
                linked_commits.append(linked_commit)

        branch = fetch_branch_for_link(github_link)
        if branch is not None:
            branch_key = (branch.repo_owner, branch.repo_name, branch.name)
            if branch_key not in seen_branch_keys:
                seen_branch_keys.add(branch_key)
                branches.append(branch)

        pull_request = fetch_pull_request_for_link(github_link)
        if pull_request is not None:
            pull_request_key = (pull_request.repo_owner, pull_request.repo_name, pull_request.number)
            if pull_request_key not in seen_pull_request_keys:
                seen_pull_request_keys.add(pull_request_key)
                pull_requests.append(pull_request)

    return CardDevelopmentResponse(
        github_links=[CardGitHubLinkResponse.model_validate(github_link) for github_link in github_links],
        recent_commits=recent_commits,
        linked_commits=linked_commits,
        branches=branches,
        pull_requests=pull_requests,
        development_status=DevelopmentStatusResponse(
            has_github_links=bool(github_links),
            link_count=len(github_links),
            commit_count=len(recent_commits),
            linked_commit_count=len(linked_commits),
            branch_count=len(branches),
            pull_request_count=len(pull_requests),
            open_pr_count=len([pull_request for pull_request in pull_requests if pull_request.state == "open"]),
            merged_pr_count=len([pull_request for pull_request in pull_requests if pull_request.merged]),
        ),
    )


def get_project_development(db: Session, project_id: int, current_user_id: int) -> ProjectDevelopmentResponse:
    ensure_project_access(db, current_user_id, project_id)
    statement = (
        select(Card)
        .where(Card.project_id == project_id, Card.archived.is_(False))
        .order_by(Card.updated_at.desc(), Card.created_at.desc(), Card.id.desc())
    )
    card_development_items = [
        ProjectCardDevelopmentResponse(
            card=CardResponse.model_validate(card),
            development=get_card_development(db, card.id, current_user_id),
        )
        for card in db.scalars(statement).all()
    ]
    return ProjectDevelopmentResponse(cards=card_development_items)


def delete_card_github_link(db: Session, github_link_id: int, current_user_id: int) -> None:
    github_link = ensure_github_link_access(db, current_user_id, github_link_id)
    card_id = github_link.card_id
    db.delete(github_link)
    create_card_activity(
        db,
        card_id=card_id,
        actor_id=current_user_id,
        action="github_link_removed",
        metadata={"github_link_id": github_link_id},
    )
    db.commit()
