from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CardGitHubLinkCreate(BaseModel):
    repo_owner: str = Field(min_length=1, max_length=120)
    repo_name: str = Field(min_length=1, max_length=120)
    branch_name: Optional[str] = Field(default=None, max_length=255)
    pull_request_number: Optional[int] = Field(default=None, gt=0)
    commit_sha: Optional[str] = Field(default=None, max_length=80)
    url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("repo_owner", "repo_name")
    @classmethod
    def validate_required_string(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Value is required")
        return normalized_value

    @field_validator("branch_name", "commit_sha", "url")
    @classmethod
    def validate_optional_string(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized_value = value.strip()
        return normalized_value or None


class CardGitHubLinkUpdate(BaseModel):
    repo_owner: Optional[str] = Field(default=None, min_length=1, max_length=120)
    repo_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    branch_name: Optional[str] = Field(default=None, max_length=255)
    pull_request_number: Optional[int] = Field(default=None, gt=0)
    commit_sha: Optional[str] = Field(default=None, max_length=80)
    url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("repo_owner", "repo_name")
    @classmethod
    def validate_required_string(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Value is required")
        return normalized_value

    @field_validator("branch_name", "commit_sha", "url")
    @classmethod
    def validate_optional_string(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized_value = value.strip()
        return normalized_value or None


class CardGitHubLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    repo_owner: str
    repo_name: str
    branch_name: Optional[str]
    pull_request_number: Optional[int]
    commit_sha: Optional[str]
    url: Optional[str]
    created_by_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class GitHubCommitResponse(BaseModel):
    sha: str
    message: str
    author_name: Optional[str]
    author_email: Optional[str]
    committed_at: Optional[str]
    url: str
    repo_owner: str
    repo_name: str
    branch_name: Optional[str]


class GitHubBranchResponse(BaseModel):
    name: str
    latest_commit_sha: str
    latest_commit_url: str
    repo_owner: str
    repo_name: str


class GitHubPullRequestResponse(BaseModel):
    number: int
    title: str
    state: str
    merged: bool
    url: str
    author: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    repo_owner: str
    repo_name: str


class DevelopmentStatusResponse(BaseModel):
    has_github_links: bool
    link_count: int
    commit_count: int
    linked_commit_count: int
    branch_count: int
    pull_request_count: int
    open_pr_count: int
    merged_pr_count: int


class CardDevelopmentResponse(BaseModel):
    github_links: list[CardGitHubLinkResponse]
    recent_commits: list[GitHubCommitResponse]
    linked_commits: list[GitHubCommitResponse]
    branches: list[GitHubBranchResponse]
    pull_requests: list[GitHubPullRequestResponse]
    development_status: DevelopmentStatusResponse
