from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.elasticsearch import es
from app.models.project import Card, CardComment, CardLabel, GitHubEvent, Project, ProjectGuest
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember


CARD_INDEX = "cards"
PROJECT_INDEX = "projects"
COMMENT_INDEX = "comments"
GITHUB_EVENT_INDEX = "github_events"


CARD_INDEX_MAPPING = {
    "properties": {
        "id": {"type": "integer"},
        "workspace_id": {"type": "integer"},
        "project_id": {"type": "integer"},
        "epic_id": {"type": "integer"},
        "sprint_id": {"type": "integer"},
        "title": {"type": "text"},
        "display_id": {"type": "text"},
        "description": {"type": "text"},
        "label_names": {"type": "text"},
        "labels": {
            "type": "nested",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "text"},
                "color": {"type": "keyword"},
            },
        },
        "status": {"type": "keyword"},
        "project_archived": {"type": "boolean"},
        "workspace_archived": {"type": "boolean"},
        "position": {"type": "integer"},
        "archived": {"type": "boolean"},
        "created_at": {"type": "date"},
        "updated_at": {"type": "date"},
    }
}

PROJECT_INDEX_MAPPING = {
    "properties": {
        "id": {"type": "integer"},
        "workspace_id": {"type": "integer"},
        "workspace_name": {"type": "text"},
        "name": {"type": "text"},
        "description": {"type": "text"},
        "position": {"type": "integer"},
        "archived": {"type": "boolean"},
        "workspace_archived": {"type": "boolean"},
        "created_at": {"type": "date"},
        "updated_at": {"type": "date"},
    }
}

COMMENT_INDEX_MAPPING = {
    "properties": {
        "id": {"type": "integer"},
        "workspace_id": {"type": "integer"},
        "project_id": {"type": "integer"},
        "card_id": {"type": "integer"},
        "card_title": {"type": "text"},
        "author_id": {"type": "integer"},
        "author_name": {"type": "text"},
        "body": {"type": "text"},
        "card_archived": {"type": "boolean"},
        "project_archived": {"type": "boolean"},
        "workspace_archived": {"type": "boolean"},
        "created_at": {"type": "date"},
        "updated_at": {"type": "date"},
    }
}

GITHUB_EVENT_INDEX_MAPPING = {
    "properties": {
        "id": {"type": "integer"},
        "workspace_id": {"type": "integer"},
        "project_id": {"type": "integer"},
        "card_id": {"type": "integer"},
        "card_title": {"type": "text"},
        "delivery_id": {"type": "keyword"},
        "installation_id": {"type": "long"},
        "repo_owner": {"type": "text"},
        "repo_name": {"type": "text"},
        "repo_full_name": {"type": "text"},
        "event_type": {"type": "keyword"},
        "action": {"type": "keyword"},
        "branch_name": {"type": "text"},
        "pull_request_number": {"type": "integer"},
        "commit_sha": {"type": "text"},
        "title": {"type": "text"},
        "message": {"type": "text"},
        "url": {"type": "keyword"},
        "sender_login": {"type": "text"},
        "card_archived": {"type": "boolean"},
        "project_archived": {"type": "boolean"},
        "workspace_archived": {"type": "boolean"},
        "created_at": {"type": "date"},
        "updated_at": {"type": "date"},
    }
}


def create_index(index_name: str, mapping: dict) -> None:
    if es.indices.exists(index=index_name):
        es.indices.put_mapping(
            index=index_name,
            properties=mapping["properties"],
        )
        return

    es.indices.create(
        index=index_name,
        mappings=mapping,
    )


def create_card_index() -> None:
    """
    Create the Elasticsearch cards index if it does not already exist.
    """

    create_index(CARD_INDEX, CARD_INDEX_MAPPING)


def create_project_index() -> None:
    create_index(PROJECT_INDEX, PROJECT_INDEX_MAPPING)


def create_comment_index() -> None:
    create_index(COMMENT_INDEX, COMMENT_INDEX_MAPPING)


def create_github_event_index() -> None:
    create_index(GITHUB_EVENT_INDEX, GITHUB_EVENT_INDEX_MAPPING)


def create_search_indices() -> None:
    create_card_index()
    create_project_index()
    create_comment_index()
    create_github_event_index()


def index_card(
    db: Session,
    card: Card,
) -> None:
    """
    Insert or update a single Card document in Elasticsearch.

    PostgreSQL remains the source of truth.
    workspace_id is denormalized from Project into the ES document.
    """

    workspace_name, workspace_archived, project_name, project_archived, workspace_id = db.execute(
        select(Workspace.name, Workspace.archived, Project.name, Project.archived, Project.workspace_id)
        .join(Project, Project.workspace_id == Workspace.id)
        .where(Project.id == card.project_id)
    ).one()
    labels = db.scalars(
        select(CardLabel)
        .where(CardLabel.card_id == card.id)
        .order_by(CardLabel.created_at.asc(), CardLabel.id.asc())
    ).all()

    document = {
        "id": card.id,
        "workspace_id": workspace_id,
        "project_id": card.project_id,
        "epic_id": card.epic_id,
        "sprint_id": card.sprint_id,
        "title": card.title,
        "display_id": f"{workspace_name}/{project_name}/{card.title}",
        "description": card.description,
        "label_names": " ".join(label.name for label in labels),
        "labels": [
            {
                "id": label.id,
                "name": label.name,
                "color": label.color,
            }
            for label in labels
        ],
        "status": card.status,
        "project_archived": project_archived,
        "workspace_archived": workspace_archived,
        "position": card.position,
        "archived": card.archived,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
    }

    es.index(
        index=CARD_INDEX,
        id=str(card.id),
        document=document,
    )


def index_project(
    project: Project,
    workspace_name: str | None = None,
    workspace_archived: bool | None = None,
) -> None:
    document = {
        "id": project.id,
        "workspace_id": project.workspace_id,
        "workspace_name": workspace_name,
        "name": project.name,
        "description": project.description,
        "position": project.position,
        "archived": project.archived,
        "workspace_archived": workspace_archived,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }

    es.index(
        index=PROJECT_INDEX,
        id=str(project.id),
        document=document,
    )


def index_comment(db: Session, comment: CardComment) -> None:
    row = db.execute(
        select(
            Project.workspace_id,
            Project.archived,
            Workspace.archived,
            Card.project_id,
            Card.title,
            Card.archived,
            User.username,
        )
        .join(Project, Project.id == Card.project_id)
        .join(Workspace, Workspace.id == Project.workspace_id)
        .join(User, User.id == comment.author_id)
        .where(Card.id == comment.card_id)
    ).one()

    workspace_id, project_archived, workspace_archived, project_id, card_title, card_archived, author_name = row
    document = {
        "id": comment.id,
        "workspace_id": workspace_id,
        "project_id": project_id,
        "card_id": comment.card_id,
        "card_title": card_title,
        "author_id": comment.author_id,
        "author_name": author_name,
        "body": comment.body,
        "card_archived": card_archived,
        "project_archived": project_archived,
        "workspace_archived": workspace_archived,
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
    }

    es.index(
        index=COMMENT_INDEX,
        id=str(comment.id),
        document=document,
    )


def index_github_event(db: Session, github_event: GitHubEvent) -> None:
    if github_event.card_id is None:
        return

    row = db.execute(
        select(
            Project.workspace_id,
            Project.archived,
            Workspace.archived,
            Card.project_id,
            Card.title,
            Card.archived,
        )
        .join(Project, Project.id == Card.project_id)
        .join(Workspace, Workspace.id == Project.workspace_id)
        .where(Card.id == github_event.card_id)
    ).one_or_none()

    if row is None:
        return

    workspace_id, project_archived, workspace_archived, project_id, card_title, card_archived = row
    document = {
        "id": github_event.id,
        "workspace_id": workspace_id,
        "project_id": project_id,
        "card_id": github_event.card_id,
        "card_title": card_title,
        "delivery_id": github_event.delivery_id,
        "installation_id": github_event.installation_id,
        "repo_owner": github_event.repo_owner,
        "repo_name": github_event.repo_name,
        "repo_full_name": (
            f"{github_event.repo_owner}/{github_event.repo_name}"
            if github_event.repo_owner and github_event.repo_name
            else None
        ),
        "event_type": github_event.event_type,
        "action": github_event.action,
        "branch_name": github_event.branch_name,
        "pull_request_number": github_event.pull_request_number,
        "commit_sha": github_event.commit_sha,
        "title": github_event.title,
        "message": github_event.message,
        "url": github_event.url,
        "sender_login": github_event.sender_login,
        "card_archived": card_archived,
        "project_archived": project_archived,
        "workspace_archived": workspace_archived,
        "created_at": github_event.created_at,
        "updated_at": github_event.updated_at,
    }

    es.index(
        index=GITHUB_EVENT_INDEX,
        id=str(github_event.id),
        document=document,
    )


def delete_card_from_index(card_id: int) -> None:
    """
    Delete a Card document from Elasticsearch.

    404 is ignored because the card may not have been indexed yet.
    """

    es.options(
        ignore_status=[404]
    ).delete(
        index=CARD_INDEX,
        id=str(card_id),
    )


def delete_project_from_index(project_id: int) -> None:
    es.options(ignore_status=[404]).delete(index=PROJECT_INDEX, id=str(project_id))


def delete_comment_from_index(comment_id: int) -> None:
    es.options(ignore_status=[404]).delete(index=COMMENT_INDEX, id=str(comment_id))


def delete_github_event_from_index(github_event_id: int) -> None:
    es.options(ignore_status=[404]).delete(index=GITHUB_EVENT_INDEX, id=str(github_event_id))


def delete_card_search_documents(card_id: int) -> dict[str, int]:
    create_search_indices()

    delete_card_from_index(card_id)
    comment_response = es.delete_by_query(
        index=COMMENT_INDEX,
        body={"query": {"term": {"card_id": card_id}}},
        ignore_unavailable=True,
        conflicts="proceed",
    )
    github_event_response = es.delete_by_query(
        index=GITHUB_EVENT_INDEX,
        body={"query": {"term": {"card_id": card_id}}},
        ignore_unavailable=True,
        conflicts="proceed",
    )

    return {
        "cards": 1,
        "comments": comment_response.get("deleted", 0),
        "github_events": github_event_response.get("deleted", 0),
    }


def delete_project_search_documents(project_id: int) -> dict[str, int]:
    create_search_indices()

    delete_project_from_index(project_id)
    card_response = es.delete_by_query(
        index=CARD_INDEX,
        body={"query": {"term": {"project_id": project_id}}},
        ignore_unavailable=True,
        conflicts="proceed",
    )
    comment_response = es.delete_by_query(
        index=COMMENT_INDEX,
        body={"query": {"term": {"project_id": project_id}}},
        ignore_unavailable=True,
        conflicts="proceed",
    )
    github_event_response = es.delete_by_query(
        index=GITHUB_EVENT_INDEX,
        body={"query": {"term": {"project_id": project_id}}},
        ignore_unavailable=True,
        conflicts="proceed",
    )

    return {
        "projects": 1,
        "cards": card_response.get("deleted", 0),
        "comments": comment_response.get("deleted", 0),
        "github_events": github_event_response.get("deleted", 0),
    }


def sync_all_cards(db: Session) -> int:
    """
    Synchronize all PostgreSQL cards into Elasticsearch.

    Useful for:
    - initial Elasticsearch setup
    - rebuilding the index
    - repairing Elasticsearch/PostgreSQL inconsistencies
    """

    cards = db.execute(
        select(Card)
    ).scalars().all()

    count = 0

    for card in cards:
        index_card(db, card)
        count += 1

    return count


def sync_all_projects(db: Session) -> int:
    rows = db.execute(
        select(Project, Workspace.name, Workspace.archived)
        .join(Workspace, Workspace.id == Project.workspace_id)
    ).all()

    count = 0
    for project, workspace_name, workspace_archived in rows:
        index_project(project, workspace_name, workspace_archived)
        count += 1

    return count


def sync_all_comments(db: Session) -> int:
    comments = db.scalars(select(CardComment)).all()

    count = 0
    for comment in comments:
        index_comment(db, comment)
        count += 1

    return count


def sync_all_github_events(db: Session) -> int:
    events = db.scalars(select(GitHubEvent).where(GitHubEvent.card_id.is_not(None))).all()

    count = 0
    for github_event in events:
        index_github_event(db, github_event)
        count += 1

    return count


def sync_all_search_documents(db: Session) -> dict[str, int]:
    create_search_indices()

    return {
        "projects": sync_all_projects(db),
        "cards": sync_all_cards(db),
        "comments": sync_all_comments(db),
        "github_events": sync_all_github_events(db),
    }


def reindex_workspace_search_documents(db: Session, workspace_id: int) -> dict[str, int]:
    create_search_indices()

    projects = list(db.scalars(select(Project).where(Project.workspace_id == workspace_id)).all())
    cards = list(
        db.scalars(
            select(Card)
            .join(Project, Project.id == Card.project_id)
            .where(Project.workspace_id == workspace_id)
        ).all()
    )
    comments = list(
        db.scalars(
            select(CardComment)
            .join(Card, Card.id == CardComment.card_id)
            .join(Project, Project.id == Card.project_id)
            .where(Project.workspace_id == workspace_id)
        ).all()
    )
    github_events = list(
        db.scalars(
            select(GitHubEvent)
            .join(Card, Card.id == GitHubEvent.card_id)
            .join(Project, Project.id == Card.project_id)
            .where(Project.workspace_id == workspace_id)
        ).all()
    )

    for project in projects:
        workspace = db.get(Workspace, project.workspace_id)
        index_project(
            project,
            workspace.name if workspace is not None else None,
            workspace.archived if workspace is not None else None,
        )

    for card in cards:
        index_card(db, card)

    for comment in comments:
        index_comment(db, comment)

    for github_event in github_events:
        index_github_event(db, github_event)

    return {
        "projects": len(projects),
        "cards": len(cards),
        "comments": len(comments),
        "github_events": len(github_events),
    }


def delete_workspace_search_documents(workspace_id: int) -> dict[str, int]:
    create_search_indices()

    project_response = es.delete_by_query(
        index=PROJECT_INDEX,
        body={"query": {"term": {"workspace_id": workspace_id}}},
        ignore_unavailable=True,
        conflicts="proceed",
    )
    card_response = es.delete_by_query(
        index=CARD_INDEX,
        body={"query": {"term": {"workspace_id": workspace_id}}},
        ignore_unavailable=True,
        conflicts="proceed",
    )
    comment_response = es.delete_by_query(
        index=COMMENT_INDEX,
        body={"query": {"term": {"workspace_id": workspace_id}}},
        ignore_unavailable=True,
        conflicts="proceed",
    )
    github_event_response = es.delete_by_query(
        index=GITHUB_EVENT_INDEX,
        body={"query": {"term": {"workspace_id": workspace_id}}},
        ignore_unavailable=True,
        conflicts="proceed",
    )

    return {
        "projects": project_response.get("deleted", 0),
        "cards": card_response.get("deleted", 0),
        "comments": comment_response.get("deleted", 0),
        "github_events": github_event_response.get("deleted", 0),
    }


def reindex_project_search_documents(db: Session, project_id: int) -> dict[str, int]:
    create_search_indices()

    project = db.get(Project, project_id)
    cards = list(db.scalars(select(Card).where(Card.project_id == project_id)).all())
    comments = list(
        db.scalars(
            select(CardComment)
            .join(Card, Card.id == CardComment.card_id)
            .where(Card.project_id == project_id)
        ).all()
    )
    github_events = list(
        db.scalars(
            select(GitHubEvent)
            .join(Card, Card.id == GitHubEvent.card_id)
            .where(Card.project_id == project_id)
        ).all()
    )

    if project is not None:
        workspace = db.get(Workspace, project.workspace_id)
        index_project(
            project,
            workspace.name if workspace is not None else None,
            workspace.archived if workspace is not None else None,
        )

    for card in cards:
        index_card(db, card)

    for comment in comments:
        index_comment(db, comment)

    for github_event in github_events:
        index_github_event(db, github_event)

    return {
        "projects": 1 if project is not None else 0,
        "cards": len(cards),
        "comments": len(comments),
        "github_events": len(github_events),
    }


def reindex_card_search_documents(db: Session, card_id: int) -> dict[str, int]:
    create_search_indices()

    card = db.get(Card, card_id)
    comments = list(db.scalars(select(CardComment).where(CardComment.card_id == card_id)).all())
    github_events = list(db.scalars(select(GitHubEvent).where(GitHubEvent.card_id == card_id)).all())

    if card is not None:
        index_card(db, card)

    for comment in comments:
        index_comment(db, comment)

    for github_event in github_events:
        index_github_event(db, github_event)

    return {
        "cards": 1 if card is not None else 0,
        "comments": len(comments),
        "github_events": len(github_events),
    }


def get_accessible_workspace_ids(
    db: Session,
    current_user_id: int,
    include_archived: bool = False,
) -> list[int]:
    member_workspace_ids = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == current_user_id)
    statement = (
        select(Workspace.id)
        .where(
            (Workspace.owner_id == current_user_id) | (Workspace.id.in_(member_workspace_ids)),
        )
        .order_by(Workspace.id.asc())
    )
    if not include_archived:
        statement = statement.where(Workspace.archived.is_(False))
    return list(db.scalars(statement).all())


def get_accessible_project_ids(
    db: Session,
    current_user_id: int,
    workspace_ids: list[int],
    include_archived: bool = False,
) -> list[int]:
    workspace_project_ids = select(Project.id).where(
        Project.workspace_id.in_(workspace_ids) if workspace_ids else False,
    )
    if not include_archived:
        workspace_project_ids = workspace_project_ids.where(Project.archived.is_(False))

    guest_project_ids = select(ProjectGuest.project_id).join(
        Project,
        Project.id == ProjectGuest.project_id,
    ).join(
        Workspace,
        Workspace.id == Project.workspace_id,
    ).where(
        ProjectGuest.user_id == current_user_id,
    )
    if not include_archived:
        guest_project_ids = guest_project_ids.where(
            Project.archived.is_(False),
            Workspace.archived.is_(False),
        )
    statement = workspace_project_ids.union(guest_project_ids)
    return list(db.scalars(statement).all())


def build_workspace_filter(workspace_ids: list[int] | int) -> dict:
    if isinstance(workspace_ids, int):
        return {"term": {"workspace_id": workspace_ids}}
    return {"terms": {"workspace_id": workspace_ids}}


def build_access_filter(
    workspace_ids: list[int] | int,
    project_ids: list[int] | None = None,
    project_field: str = "project_id",
) -> dict:
    workspace_filter = build_workspace_filter(workspace_ids)

    if not project_ids:
        return workspace_filter

    return {
        "bool": {
            "should": [
                workspace_filter,
                {"terms": {project_field: project_ids}},
            ],
            "minimum_should_match": 1,
        }
    }


def search_cards(
    workspace_id: int | list[int],
    query: str,
    project_ids: list[int] | None = None,
    include_archived: bool = False,
    limit: int = 20,
) -> list[dict]:
    normalized_query = query.strip()

    if not normalized_query:
        return []

    filters = [build_access_filter(workspace_id, project_ids)]
    if not include_archived:
        filters.extend(
            [
                {"term": {"archived": False}},
                {"term": {"project_archived": False}},
                {"term": {"workspace_archived": False}},
            ]
        )

    response = es.search(
        index=CARD_INDEX,
        size=limit,
        query={
            "bool": {
                "filter": filters,
                "should": [
                    {
                        "match_phrase": {
                            "title": {
                                "query": normalized_query,
                                "boost": 6,
                            }
                        }
                    },
                    {
                        "match_phrase": {
                            "label_names": {
                                "query": normalized_query,
                                "boost": 5,
                            }
                        }
                    },
                    {
                        "multi_match": {
                            "query": normalized_query,
                            "fields": [
                                "title^3",
                                "description^2",
                                "label_names^3",
                            ],
                            "boost": 3,
                        }
                    },
                    {
                        "multi_match": {
                            "query": normalized_query,
                            "fields": [
                                "title^2",
                                "description",
                                "label_names^2",
                            ],
                            "fuzziness": "AUTO",
                            "boost": 0.5,
                        }
                    },
                ],
                "minimum_should_match": 1,
            }
        },
    )

    return [
        {
            **hit["_source"],
            "_score": hit["_score"],
        }
        for hit in response["hits"]["hits"]
    ]


def search_projects(
    workspace_id: int | list[int],
    query: str,
    project_ids: list[int] | None = None,
    include_archived: bool = False,
    limit: int = 10,
) -> list[dict]:
    normalized_query = query.strip()

    if not normalized_query:
        return []

    filters = [build_access_filter(workspace_id, project_ids, project_field="id")]
    if not include_archived:
        filters.extend(
            [
                {"term": {"archived": False}},
                {"term": {"workspace_archived": False}},
            ]
        )

    response = es.search(
        index=PROJECT_INDEX,
        size=limit,
        query={
            "bool": {
                "filter": filters,
                "should": [
                    {"match_phrase": {"name": {"query": normalized_query, "boost": 6}}},
                    {
                        "multi_match": {
                            "query": normalized_query,
                            "fields": ["name^3", "description", "workspace_name"],
                            "boost": 3,
                        }
                    },
                    {
                        "multi_match": {
                            "query": normalized_query,
                            "fields": ["name^2", "description", "workspace_name"],
                            "fuzziness": "AUTO",
                            "boost": 0.5,
                        }
                    },
                ],
                "minimum_should_match": 1,
            }
        },
    )

    return [
        {
            **hit["_source"],
            "_score": hit["_score"],
        }
        for hit in response["hits"]["hits"]
    ]


def search_comments(
    workspace_id: int | list[int],
    query: str,
    project_ids: list[int] | None = None,
    include_archived: bool = False,
    limit: int = 10,
) -> list[dict]:
    normalized_query = query.strip()

    if not normalized_query:
        return []

    filters = [build_access_filter(workspace_id, project_ids)]
    if not include_archived:
        filters.extend(
            [
                {"term": {"card_archived": False}},
                {"term": {"project_archived": False}},
                {"term": {"workspace_archived": False}},
            ]
        )

    response = es.search(
        index=COMMENT_INDEX,
        size=limit,
        query={
            "bool": {
                "filter": filters,
                "should": [
                    {"match_phrase": {"body": {"query": normalized_query, "boost": 6}}},
                    {
                        "multi_match": {
                            "query": normalized_query,
                            "fields": ["body^3", "card_title^2", "author_name"],
                            "boost": 3,
                        }
                    },
                    {
                        "multi_match": {
                            "query": normalized_query,
                            "fields": ["body^2", "card_title", "author_name"],
                            "fuzziness": "AUTO",
                            "boost": 0.5,
                        }
                    },
                ],
                "minimum_should_match": 1,
            }
        },
    )

    return [
        {
            **hit["_source"],
            "_score": hit["_score"],
        }
        for hit in response["hits"]["hits"]
    ]


def search_github_events(
    workspace_id: int | list[int],
    query: str,
    project_ids: list[int] | None = None,
    include_archived: bool = False,
    limit: int = 10,
) -> list[dict]:
    normalized_query = query.strip()

    if not normalized_query:
        return []

    filters = [build_access_filter(workspace_id, project_ids)]
    if not include_archived:
        filters.extend(
            [
                {"term": {"card_archived": False}},
                {"term": {"project_archived": False}},
                {"term": {"workspace_archived": False}},
            ]
        )

    response = es.search(
        index=GITHUB_EVENT_INDEX,
        size=limit,
        query={
            "bool": {
                "filter": filters,
                "should": [
                    {"match_phrase": {"message": {"query": normalized_query, "boost": 6}}},
                    {"match_phrase": {"title": {"query": normalized_query, "boost": 5}}},
                    {
                        "multi_match": {
                            "query": normalized_query,
                            "fields": [
                                "repo_full_name^4",
                                "message^3",
                                "title^3",
                                "commit_sha^2",
                                "branch_name^2",
                                "sender_login",
                                "card_title",
                            ],
                            "boost": 3,
                        }
                    },
                    {
                        "multi_match": {
                            "query": normalized_query,
                            "fields": [
                                "repo_full_name^3",
                                "message^2",
                                "title^2",
                                "branch_name",
                                "sender_login",
                                "card_title",
                            ],
                            "fuzziness": "AUTO",
                            "boost": 0.5,
                        }
                    },
                ],
                "minimum_should_match": 1,
            }
        },
    )

    return [
        {
            **hit["_source"],
            "_score": hit["_score"],
        }
        for hit in response["hits"]["hits"]
    ]


def to_search_item(item_type: str, source: dict) -> dict:
    item = {
        "type": item_type,
        "id": source["id"],
        "workspace_id": source.get("workspace_id"),
        "project_id": source.get("project_id"),
        "card_id": source.get("card_id"),
        "comment_id": source["id"] if item_type == "comment" else None,
        "github_event_id": source["id"] if item_type == "github_event" else None,
        "score": source.get("_score"),
    }

    if item_type == "project":
        item.update(
            {
                "title": source.get("name"),
                "subtitle": source.get("workspace_name"),
                "description": source.get("description"),
                "archived": source.get("archived"),
                "workspace_archived": source.get("workspace_archived"),
                "url": f"/workspaces/{source.get('workspace_id')}/projects/{source.get('id')}",
            }
        )
    elif item_type == "card":
        item.update(
            {
                "title": source.get("title"),
                "subtitle": source.get("display_id"),
                "description": source.get("description"),
                "label_names": source.get("label_names"),
                "labels": source.get("labels", []),
                "status": source.get("status"),
                "archived": source.get("archived"),
                "project_archived": source.get("project_archived"),
                "workspace_archived": source.get("workspace_archived"),
                "url": f"/workspaces/{source.get('workspace_id')}/projects/{source.get('project_id')}/cards/{source.get('id')}",
            }
        )
    elif item_type == "comment":
        item.update(
            {
                "title": source.get("card_title"),
                "subtitle": source.get("author_name"),
                "description": source.get("body"),
                "card_archived": source.get("card_archived"),
                "project_archived": source.get("project_archived"),
                "workspace_archived": source.get("workspace_archived"),
                "created_at": source.get("created_at"),
                "url": f"/workspaces/{source.get('workspace_id')}/projects/{source.get('project_id')}/cards/{source.get('card_id')}?focus=comments&commentId={source.get('id')}",
            }
        )
    elif item_type == "github_event":
        repo_name = source.get("repo_full_name") or "/".join(
            value for value in [source.get("repo_owner"), source.get("repo_name")] if value
        )
        event_title = source.get("title") or source.get("message") or source.get("event_type")
        item.update(
            {
                "title": event_title,
                "subtitle": repo_name,
                "description": source.get("message"),
                "event_type": source.get("event_type"),
                "branch_name": source.get("branch_name"),
                "commit_sha": source.get("commit_sha"),
                "sender_login": source.get("sender_login"),
                "card_archived": source.get("card_archived"),
                "project_archived": source.get("project_archived"),
                "workspace_archived": source.get("workspace_archived"),
                "created_at": source.get("created_at"),
                "external_url": source.get("url"),
                "url": f"/workspaces/{source.get('workspace_id')}/projects/{source.get('project_id')}/cards/{source.get('card_id')}?focus=development&eventId={source.get('id')}",
            }
        )

    return item


def search_workspace(
    workspace_id: int | list[int],
    query: str,
    project_ids: list[int] | None = None,
    include_archived: bool = False,
    limit: int = 10,
) -> dict[str, list[dict]]:
    projects = search_projects(workspace_id, query, project_ids, include_archived, limit)
    cards = search_cards(workspace_id, query, project_ids, include_archived, limit)
    comments = search_comments(workspace_id, query, project_ids, include_archived, limit)
    github_events = search_github_events(workspace_id, query, project_ids, include_archived, limit)

    return {
        "projects": projects,
        "cards": cards,
        "comments": comments,
        "github_events": github_events,
        "items": [
            *[to_search_item("project", project) for project in projects],
            *[to_search_item("card", card) for card in cards],
            *[to_search_item("comment", comment) for comment in comments],
            *[to_search_item("github_event", github_event) for github_event in github_events],
        ],
    }
