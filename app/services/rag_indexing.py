"""
将 Projectly 数据转换为统一的 RAG chunks
rag_indexing.py
读取数据库对象
→ 构建可检索文本
→ rag_chunking.chunk_text()
→ rag_embedding.create_embeddings()
→ 原子替换 rag_chunks

Card：
- title、description、status、labels、members 和 linked work items
  作为同一个逻辑 source。
- 长文本可以切成多个 chunks。
- source_type="card"
- source_id=card.id

Comment：
- 每条 Comment 是独立 source，不与其他 Comments 合并。
- 文本包含 Card title、Comment author 和 Comment body。
- source_type="comment"
- source_id=comment.id

Attachment：
- 每个 Attachment 是独立 source。
- PDF 先由 Docling 转换为 Markdown/JSON，再进行 chunking。
- source_type="attachment"
- source_id=attachment.id

Workspace、Project、Epic、Sprint：
- 每个业务对象独立构建文本并进行 chunking。
- 分别使用 workspace、project、epic、sprint 作为 source_type。
- source_id 使用对应业务对象的主键。

GitHub Event：
- 每个 Event 是独立 source。
- 文本包含 repository、event type、action、branch、PR、commit 和 message。
- source_type="github_event"
- source_id=github_event.id

所有来源最终统一写入 rag_chunks，并保存：
- workspace_id
- project_id
- card_id
- source_type
- source_id
- source_subtype
- chunk_index
- title
- content
- token_count
- page_number
- embedding
- metadata
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.project import (
    AttachmentDocument, Card, CardAttachment,
    CardComment, Project, RagChunk, Epic, Sprint, GitHubEvent
)
from app.models.user import User
from app.models.workspace import Workspace
from app.services.rag_chunking import RagChunkDraft, chunk_text
from app.services.rag_embedding import create_embeddings
from sqlalchemy import or_

from app.models.project import (
    Card,
    CardLabel,
    CardLink,
    CardMember,
)

# 删除某个来源的旧索引
def delete_source_chunks(
    db: Session,
    source_type: str,
    source_id: int,
) -> None:
    db.execute(
        delete(RagChunk).where(
            RagChunk.source_type == source_type,
            RagChunk.source_id == source_id,
        )
    )

# 通用保存函数：先生成embedding，再删除旧数据
def replace_source_chunks(
    db: Session,
    *,
    workspace_id: int,
    project_id: int | None,
    card_id: int | None,
    source_type: str,
    source_id: int,
    source_subtype: str,
    title: str | None,
    text: str,
    metadata: dict | None = None,
) -> list[RagChunk]:
    drafts = chunk_text(text, metadata=metadata)
    embeddings = create_embeddings([draft.content for draft in drafts])

    delete_source_chunks(db, source_type, source_id)

    chunks = [
        RagChunk(
            workspace_id=workspace_id,
            project_id=project_id,
            card_id=card_id,
            source_type=source_type,
            source_id=source_id,
            source_subtype=source_subtype,
            chunk_index=draft.chunk_index,
            title=title,
            content=draft.content,
            embedding=embedding,
            chunk_metadata={
                **draft.metadata,
                "token_count": draft.token_count,
                "page_number": draft.page_number,
            },
        )
        for draft, embedding in zip(drafts, embeddings, strict=True)
    ]

    db.add_all(chunks)
    db.commit()
    return chunks

"""
card
"""
# 构建card文本
def build_card_text(
    card: Card,
    labels: list[str],
    members: list[str],
    linked_items: list[str],
) -> str:
    parts = [
        f"Card title: {card.title}",
        f"Status: {card.status}",
    ]

    if card.description:
        parts.append(f"Description:\n{card.description}")

    if labels:
        parts.append(f"Labels: {', '.join(labels)}")

    if members:
        parts.append(f"Members: {', '.join(members)}")

    if linked_items:
        parts.append(
            "Linked work items:\n- " + "\n- ".join(linked_items)
        )

    return "\n\n".join(parts)

# card indexing
def index_card(db: Session, card_id: int) -> list[RagChunk]:
    card = db.get(Card, card_id)
    if card is None:
        return []

    project = db.get(Project, card.project_id)
    if project is None:
        return []

    labels = list(
      db.scalars(
          select(CardLabel.name)
          .where(CardLabel.card_id == card.id)
          .order_by(CardLabel.name)
      ).all()
    )

    members = list(
      db.scalars(
          select(User.username)
          .join(CardMember, CardMember.user_id == User.id)
          .where(CardMember.card_id == card.id)
          .order_by(User.username)
      ).all()
    )

    links = list(
      db.scalars(
          select(CardLink).where(
              or_(
                  CardLink.source_card_id == card.id,
                  CardLink.target_card_id == card.id,
              )
          )
      ).all()
    )

    linked_items: list[str] = []

    for link in links:
      source_card = db.get(Card, link.source_card_id)
      target_card = db.get(Card, link.target_card_id)

      if source_card is None or target_card is None:
          continue

      linked_items.append(
          f"{source_card.title} "
          f"{link.relationship.replace('_', ' ')} "
          f"{target_card.title}"
      )

    return replace_source_chunks(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        card_id=card.id,
        source_type="card",
        source_id=card.id,
        source_subtype="card_details",
        title=card.title,
        text=build_card_text(
            card,
            labels,
            members,
            linked_items,
        ),
        metadata={
            "status": card.status,
            "epic_id": card.epic_id,
            "sprint_id": card.sprint_id,
            "archived": card.archived,
            "labels": labels,
            "members": members,
            "linked_items": linked_items,
        },
    )

"""
comment
"""
# 构建comment文本
def build_comment_text(
    comment: CardComment,
    card: Card,
    author: User | None,
) -> str:
    author_name = author.username if author else f"user-{comment.author_id}"

    return "\n\n".join(
        [
            f"Card: {card.title}",
            f"Comment author: {author_name}",
            f"Comment:\n{comment.body}",
        ]
    )

# comment indexing
def index_comment(db: Session, comment_id: int) -> list[RagChunk]:
    comment = db.get(CardComment, comment_id)
    if comment is None:
        return []

    card = db.get(Card, comment.card_id)
    if card is None:
        return []

    project = db.get(Project, card.project_id)
    if project is None:
        return []

    author = db.get(User, comment.author_id)

    return replace_source_chunks(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        card_id=card.id,
        source_type="comment",
        source_id=comment.id,
        source_subtype="comment_body",
        title=card.title,
        text=build_comment_text(comment, card, author),
        metadata={
            "author_id": comment.author_id,
            "author_name": author.username if author else None,
            "card_title": card.title,
        },
    )

"""
attachment
"""
# attachment indexing
def index_attachment(
    db: Session,
    attachment_id: int,
) -> list[RagChunk]:
    attachment = db.get(CardAttachment, attachment_id)
    if attachment is None:
        return []

    document = db.scalar(
        select(AttachmentDocument).where(
            AttachmentDocument.attachment_id == attachment.id
        )
    )

    if (
        document is None
        or document.extraction_status != "completed"
        or not document.content_markdown
    ):
        raise RuntimeError(
            "Attachment extraction must be completed before indexing"
        )

    card = db.get(Card, attachment.card_id)
    if card is None:
        return []

    project = db.get(Project, card.project_id)
    if project is None:
        return []

    return replace_source_chunks(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        card_id=card.id,
        source_type="attachment",
        source_id=attachment.id,
        source_subtype="attachment_pdf",
        title=attachment.file_name,
        text=document.content_markdown,
        metadata={
            "attachment_id": attachment.id,
            "file_name": attachment.file_name,
            "file_type": attachment.file_type,
            "file_size": attachment.file_size,
            "attachment_document_id": document.id,
        },
    )

"""
Workspace
"""
# Workspace
def build_workspace_text(
    workspace: Workspace,
    owner: User | None,
) -> str:
    parts = [
        f"Workspace name: {workspace.name}",
        f"Archived: {workspace.archived}",
    ]

    if owner:
        parts.append(f"Owner: {owner.username}")

    return "\n\n".join(parts)


def index_workspace(
    db: Session,
    workspace_id: int,
) -> list[RagChunk]:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        return []

    owner = db.get(User, workspace.owner_id)

    return replace_source_chunks(
        db,
        workspace_id=workspace.id,
        project_id=None,
        card_id=None,
        source_type="workspace",
        source_id=workspace.id,
        source_subtype="workspace_details",
        title=workspace.name,
        text=build_workspace_text(workspace, owner),
        metadata={
            "owner_id": workspace.owner_id,
            "owner_name": owner.username if owner else None,
            "archived": workspace.archived,
        },
    )

"""
Project
"""
def build_project_text(project: Project) -> str:
    parts = [
        f"Project name: {project.name}",
        f"Archived: {project.archived}",
    ]

    if project.description:
        parts.append(f"Description:\n{project.description}")

    return "\n\n".join(parts)


def index_project(
    db: Session,
    project_id: int,
) -> list[RagChunk]:
    project = db.get(Project, project_id)
    if project is None:
        return []

    return replace_source_chunks(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        card_id=None,
        source_type="project",
        source_id=project.id,
        source_subtype="project_details",
        title=project.name,
        text=build_project_text(project),
        metadata={
            "archived": project.archived,
        },
    )

"""
Epic
"""
def build_epic_text(epic: Epic, project: Project) -> str:
    parts = [
        f"Epic title: {epic.title}",
        f"Project: {project.name}",
        f"Archived: {epic.archived}",
    ]

    if epic.deadline:
        parts.append(f"Deadline: {epic.deadline.isoformat()}")

    return "\n\n".join(parts)


def index_epic(db: Session, epic_id: int) -> list[RagChunk]:
    epic = db.get(Epic, epic_id)
    if epic is None:
        return []

    project = db.get(Project, epic.project_id)
    if project is None:
        return []

    return replace_source_chunks(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        card_id=None,
        source_type="epic",
        source_id=epic.id,
        source_subtype="epic_details",
        title=epic.title,
        text=build_epic_text(epic, project),
        metadata={
            "deadline": (
                epic.deadline.isoformat()
                if epic.deadline
                else None
            ),
            "archived": epic.archived,
        },
    )

"""
Sprint
"""
def build_sprint_text(
    sprint: Sprint,
    epic: Epic,
    project: Project,
) -> str:
    parts = [
        f"Sprint name: {sprint.name}",
        f"Status: {sprint.status}",
        f"Epic: {epic.title}",
        f"Project: {project.name}",
    ]

    if sprint.goal:
        parts.append(f"Goal:\n{sprint.goal}")

    if sprint.start_date:
        parts.append(f"Start date: {sprint.start_date.isoformat()}")

    if sprint.end_date:
        parts.append(f"End date: {sprint.end_date.isoformat()}")

    parts.append(f"Archived: {sprint.archived}")

    return "\n\n".join(parts)

def index_sprint(db: Session, sprint_id: int) -> list[RagChunk]:
    sprint = db.get(Sprint, sprint_id)
    if sprint is None:
        return []

    epic = db.get(Epic, sprint.epic_id)
    if epic is None:
        return []

    project = db.get(Project, epic.project_id)
    if project is None:
        return []

    return replace_source_chunks(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        card_id=None,
        source_type="sprint",
        source_id=sprint.id,
        source_subtype="sprint_details",
        title=sprint.name,
        text=build_sprint_text(sprint, epic, project),
        metadata={
            "epic_id": epic.id,
            "status": sprint.status,
            "start_date": sprint.start_date.isoformat() if sprint.start_date else None,
            "end_date": sprint.end_date.isoformat() if sprint.end_date else None,
            "archived": sprint.archived,
        },
    )

"""
Github Event
"""
def build_github_event_text(event: GitHubEvent) -> str:
    repository = "/".join(
        part for part in [event.repo_owner, event.repo_name] if part
    )

    parts = [
        f"GitHub event type: {event.event_type}",
    ]

    if repository:
        parts.append(f"Repository: {repository}")
    if event.action:
        parts.append(f"Action: {event.action}")
    if event.title:
        parts.append(f"Title: {event.title}")
    if event.message:
        parts.append(f"Message:\n{event.message}")
    if event.branch_name:
        parts.append(f"Branch: {event.branch_name}")
    if event.pull_request_number:
        parts.append(f"Pull request: #{event.pull_request_number}")
    if event.commit_sha:
        parts.append(f"Commit: {event.commit_sha}")
    if event.sender_login:
        parts.append(f"Sender: {event.sender_login}")

    return "\n\n".join(parts)

def index_github_event(
    db: Session,
    github_event_id: int,
) -> list[RagChunk]:
    event = db.get(GitHubEvent, github_event_id)
    if event is None:
        return []

    if event.card_id is None:
        delete_source_chunks(db, "github_event", event.id)
        db.commit()
        return []

    card = db.get(Card, event.card_id)
    if card is None:
        return []

    project = db.get(Project, card.project_id)
    if project is None:
        return []

    title = event.title or f"GitHub {event.event_type} event"

    return replace_source_chunks(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        card_id=card.id,
        source_type="github_event",
        source_id=event.id,
        source_subtype=f"github_{event.event_type}",
        title=title,
        text=build_github_event_text(event),
        metadata={
            "event_type": event.event_type,
            "action": event.action,
            "repo_owner": event.repo_owner,
            "repo_name": event.repo_name,
            "branch_name": event.branch_name,
            "pull_request_number": event.pull_request_number,
            "commit_sha": event.commit_sha,
            "sender_login": event.sender_login,
            "url": event.url,
        },
    )