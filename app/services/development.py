import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.project import CardGitHubLink
from app.schemas.development import (
    CardDevelopmentResponse,
    CardGitHubLinkCreate,
    CardGitHubLinkResponse,
    GitHubCommitResponse,
)
from app.services.activities import create_card_activity
from app.services.cards import ensure_card_access


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


def fetch_recent_commits_for_link(github_link: CardGitHubLink) -> list[GitHubCommitResponse]:
    if not github_link.branch_name:
        return []

    params = urlencode({"sha": github_link.branch_name, "per_page": 5})
    url = f"https://api.github.com/repos/{github_link.repo_owner}/{github_link.repo_name}/commits?{params}"
    request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "Projectly"})

    try:
        with urlopen(request, timeout=8) as response:
            commits = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return []
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitHub commits request failed") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitHub commits request failed") from exc

    recent_commits: list[GitHubCommitResponse] = []
    for commit_item in commits:
        commit = commit_item.get("commit", {})
        author = commit.get("author") or {}
        recent_commits.append(
            GitHubCommitResponse(
                sha=commit_item.get("sha", ""),
                message=commit.get("message", ""),
                author_name=author.get("name"),
                author_email=author.get("email"),
                committed_at=author.get("date"),
                url=commit_item.get("html_url", ""),
                repo_owner=github_link.repo_owner,
                repo_name=github_link.repo_name,
                branch_name=github_link.branch_name,
            )
        )
    return recent_commits


def get_card_development(db: Session, card_id: int, current_user_id: int) -> CardDevelopmentResponse:
    github_links = list_card_github_links(db, card_id, current_user_id)
    recent_commits: list[GitHubCommitResponse] = []
    seen_commit_keys: set[tuple[str, str, str]] = set()

    for github_link in github_links:
        for commit in fetch_recent_commits_for_link(github_link):
            commit_key = (commit.repo_owner, commit.repo_name, commit.sha)
            if commit_key in seen_commit_keys:
                continue
            seen_commit_keys.add(commit_key)
            recent_commits.append(commit)

    return CardDevelopmentResponse(
        github_links=[CardGitHubLinkResponse.model_validate(github_link) for github_link in github_links],
        recent_commits=recent_commits,
    )


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
