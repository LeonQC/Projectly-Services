"""
负责 Attachment 的完整处理任务和状态管理
create_rag_ingestion_job()
→ 创建 pending job

enqueue_rag_ingestion_job()
→ 调用 rag_events.py 发送 Kafka 消息

run_rag_ingestion_job()
→ 真正运行 Extraction + Indexing

mark_job_processing()
→ 标记 processing

mark_job_completed()
→ 标记 completed

mark_job_failed()
→ 记录失败原因和 retry_count

reprocess_attachment_rag()
→ 人工要求重新处理 Attachment
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.project import (
    AttachmentDocument,
    CardAttachment,
    RagChunk,
    RagIngestionJob,
)
from app.services.attachment_extraction import extract_attachment_document
from app.services.attachments import ensure_attachment_access
from app.services.rag_events import publish_attachment_ingestion_event
from app.services.rag_indexing import index_attachment

# job创建和发送
def create_rag_ingestion_job(
    db: Session,
    attachment_id: int,
    current_user_id: int,
) -> RagIngestionJob:
    attachment = ensure_attachment_access(
        db, current_user_id, attachment_id
    )

    job = RagIngestionJob(
        attachment_id=attachment.id,
        card_id=attachment.card_id,
        requested_by_id=current_user_id,
        status="pending",
        retry_count=0,
        error_message=None,
    )

    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def enqueue_rag_ingestion_job(
    job: RagIngestionJob,
    *,
    event_type: str = "attachment.uploaded",
) -> None:
    publish_attachment_ingestion_event(
        event_type,
        {
            "job_id": job.id,
            "attachment_id": job.attachment_id,
            "card_id": job.card_id,
            "uploaded_by_id": job.requested_by_id,
        },
    )

# 清理旧结果
def reset_attachment_rag_outputs(
    db: Session,
    attachment_id: int,
) -> None:
    db.execute(
        delete(RagChunk).where(
            RagChunk.source_type == "attachment",
            RagChunk.source_id == attachment_id,
        )
    )
    db.execute(
        delete(AttachmentDocument).where(
            AttachmentDocument.attachment_id == attachment_id,
        )
    )

# job状态
def mark_job_processing(db: Session, job: RagIngestionJob) -> None:
    job.status = "processing"
    job.error_message = None
    job.started_at = datetime.now(timezone.utc)
    job.completed_at = None
    db.commit()


def mark_job_completed(db: Session, job: RagIngestionJob) -> None:
    job.status = "completed"
    job.error_message = None
    job.completed_at = datetime.now(timezone.utc)
    db.commit()


def mark_job_failed(
    db: Session,
    job: RagIngestionJob,
    error: Exception,
) -> None:
    job.status = "failed"
    job.retry_count += 1
    job.error_message = str(error)
    job.completed_at = datetime.now(timezone.utc)
    db.commit()

# 真正运行任务
def run_rag_ingestion_job(
    db: Session,
    attachment_id: int,
    current_user_id: int,
    *,
    job_id: int,
    force: bool = False,
) -> RagIngestionJob:
    attachment = ensure_attachment_access(
        db, current_user_id, attachment_id
    )

    job = db.get(RagIngestionJob, job_id)

    if job is None or job.attachment_id != attachment.id:
        raise ValueError("RAG ingestion job does not match attachment")

    if job.status == "completed" and not force:
        return job

    mark_job_processing(db, job)

    try:
        if force:
            reset_attachment_rag_outputs(db, attachment.id)
            db.commit()

        extract_attachment_document(
            db,
            attachment.id,
            current_user_id,
            force=force,
        )

        index_attachment(db, attachment.id)

        db.refresh(job)
        mark_job_completed(db, job)
        db.refresh(job)
        return job

    except Exception as exc:
        db.rollback()

        failed_job = db.get(RagIngestionJob, job.id)
        if failed_job is not None:
            mark_job_failed(db, failed_job, exc)

        raise

# 手动reporcess
def reprocess_attachment_rag(
    db: Session,
    attachment_id: int,
    current_user_id: int,
) -> RagIngestionJob:
    attachment = ensure_attachment_access(
        db, current_user_id, attachment_id
    )

    if attachment.file_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF attachments can be reprocessed",
        )

    job = create_rag_ingestion_job(
        db,
        attachment.id,
        current_user_id,
    )

    enqueue_rag_ingestion_job(
        job,
        event_type="attachment.reprocess",
    )

    return job