from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.elasticsearch import es
from app.models.project import Card, CardComment, Project
from app.models.user import User
from app.models.workspace import Workspace


CARD_INDEX = "cards"
PROJECT_INDEX = "projects"
COMMENT_INDEX = "comments"


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
        "status": {"type": "keyword"},
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
        "created_at": {"type": "date"},
        "updated_at": {"type": "date"},
    }
}


def create_index(index_name: str, mapping: dict) -> None:
    if es.indices.exists(index=index_name):
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


def create_search_indices() -> None:
    create_card_index()
    create_project_index()
    create_comment_index()


def index_card(
    db: Session,
    card: Card,
) -> None:
    """
    Insert or update a single Card document in Elasticsearch.

    PostgreSQL remains the source of truth.
    workspace_id is denormalized from Project into the ES document.
    """

    workspace_name, project_name, workspace_id = db.execute(
        select(Workspace.name, Project.name, Project.workspace_id)
        .join(Project, Project.workspace_id == Workspace.id)
        .where(Project.id == card.project_id)
    ).one()

    document = {
        "id": card.id,
        "workspace_id": workspace_id,
        "project_id": card.project_id,
        "epic_id": card.epic_id,
        "sprint_id": card.sprint_id,
        "title": card.title,
        "display_id": f"{workspace_name}/{project_name}/{card.title}",
        "description": card.description,
        "status": card.status,
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


def index_project(project: Project, workspace_name: str | None = None) -> None:
    document = {
        "id": project.id,
        "workspace_id": project.workspace_id,
        "workspace_name": workspace_name,
        "name": project.name,
        "description": project.description,
        "position": project.position,
        "archived": project.archived,
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
            Card.project_id,
            Card.title,
            User.username,
        )
        .join(Project, Project.id == Card.project_id)
        .join(User, User.id == comment.author_id)
        .where(Card.id == comment.card_id)
    ).one()

    workspace_id, project_id, card_title, author_name = row
    document = {
        "id": comment.id,
        "workspace_id": workspace_id,
        "project_id": project_id,
        "card_id": comment.card_id,
        "card_title": card_title,
        "author_id": comment.author_id,
        "author_name": author_name,
        "body": comment.body,
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
    }

    es.index(
        index=COMMENT_INDEX,
        id=str(comment.id),
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
        select(Project, Workspace.name)
        .join(Workspace, Workspace.id == Project.workspace_id)
    ).all()

    count = 0
    for project, workspace_name in rows:
        index_project(project, workspace_name)
        count += 1

    return count


def sync_all_comments(db: Session) -> int:
    comments = db.scalars(select(CardComment)).all()

    count = 0
    for comment in comments:
        index_comment(db, comment)
        count += 1

    return count


def sync_all_search_documents(db: Session) -> dict[str, int]:
    create_search_indices()

    return {
        "projects": sync_all_projects(db),
        "cards": sync_all_cards(db),
        "comments": sync_all_comments(db),
    }


def search_cards(
    workspace_id: int,
    query: str,
    limit: int = 20,
) -> list[dict]:
    normalized_query = query.strip()

    if not normalized_query:
        return []

    response = es.search(
        index=CARD_INDEX,
        size=limit,
        query={
            "bool": {
                "filter": [
                    {
                        "term": {
                            "workspace_id": workspace_id,
                        }
                    },
                    {
                        "term": {
                            "archived": False,
                        }
                    },
                ],
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
                        "multi_match": {
                            "query": normalized_query,
                            "fields": [
                                "title^3",
                                "description",
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
    workspace_id: int,
    query: str,
    limit: int = 10,
) -> list[dict]:
    normalized_query = query.strip()

    if not normalized_query:
        return []

    response = es.search(
        index=PROJECT_INDEX,
        size=limit,
        query={
            "bool": {
                "filter": [
                    {"term": {"workspace_id": workspace_id}},
                    {"term": {"archived": False}},
                ],
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
    workspace_id: int,
    query: str,
    limit: int = 10,
) -> list[dict]:
    normalized_query = query.strip()

    if not normalized_query:
        return []

    response = es.search(
        index=COMMENT_INDEX,
        size=limit,
        query={
            "bool": {
                "filter": [
                    {"term": {"workspace_id": workspace_id}},
                ],
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


def search_workspace(
    workspace_id: int,
    query: str,
    limit: int = 10,
) -> dict[str, list[dict]]:
    return {
        "projects": search_projects(workspace_id, query, limit),
        "cards": search_cards(workspace_id, query, limit),
        "comments": search_comments(workspace_id, query, limit),
    }
