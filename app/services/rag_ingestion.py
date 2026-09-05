from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.project import AttachmentChunk, AttachmentDocument, CardAttachment, RagIngestionJob
from app.services.attachment_chunking import chunk_attachment_document
from app.services.attachment_embeddings import embed_attachment_chunks
from app.services.attachment_extraction import extract_attachment_document
from app.services.attachments import ensure_attachment_access
from app.services.rag_events import publish_rag_event


def create_rag_ingestion_job(
    db: Session,
    attachment_id: int,
    current_user_id: int,
) -> RagIngestionJob:
    attachment = ensure_attachment_access(db, current_user_id, attachment_id)
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


def enqueue_rag_ingestion_job(job: RagIngestionJob) -> None:
    publish_rag_event(
        "attachment.uploaded",
        {
            "job_id": job.id,
            "attachment_id": job.attachment_id,
            "card_id": job.card_id,
            "uploaded_by_id": job.requested_by_id,
        },
    )


def get_or_create_rag_ingestion_job(
    db: Session,
    attachment_id: int,
    current_user_id: int,
    *,
    job_id: int | None = None,
) -> RagIngestionJob:
    if job_id is not None:
        job = db.get(RagIngestionJob, job_id)
        if job is not None:
            return job

    job = db.scalar(
        select(RagIngestionJob)
        .where(
            RagIngestionJob.attachment_id == attachment_id,
            RagIngestionJob.status.in_(("pending", "processing")),
        )
        .order_by(RagIngestionJob.created_at.desc(), RagIngestionJob.id.desc())
    )
    if job is not None:
        return job

    return create_rag_ingestion_job(db, attachment_id, current_user_id)


def reset_attachment_rag_outputs(db: Session, attachment_id: int) -> None:
    db.execute(delete(AttachmentChunk).where(AttachmentChunk.attachment_id == attachment_id))
    db.execute(delete(AttachmentDocument).where(AttachmentDocument.attachment_id == attachment_id))


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


def mark_job_failed(db: Session, job: RagIngestionJob, error: Exception) -> None:
    job.status = "failed"
    job.retry_count += 1
    job.error_message = str(error)
    job.completed_at = datetime.now(timezone.utc)
    db.commit()


def run_rag_ingestion_job(
    db: Session,
    attachment_id: int,
    current_user_id: int,
    *,
    job_id: int | None = None,
    force: bool = False,
) -> RagIngestionJob:
    attachment = ensure_attachment_access(db, current_user_id, attachment_id)
    job = get_or_create_rag_ingestion_job(
        db,
        attachment.id,
        current_user_id,
        job_id=job_id,
    )

    if job.status == "completed" and not force:
        return job

    mark_job_processing(db, job)

    try:
        if force:
            reset_attachment_rag_outputs(db, attachment.id)
            db.commit()

        extract_attachment_document(db, attachment.id, current_user_id, force=force)
        chunk_attachment_document(db, attachment.id, current_user_id)
        embed_attachment_chunks(db, attachment.id, current_user_id)
        db.refresh(job)
        mark_job_completed(db, job)
        db.refresh(job)
        return job
    except Exception as exc:
        db.rollback()
        job = db.get(RagIngestionJob, job.id)
        if job is not None:
            mark_job_failed(db, job, exc)
        raise


def reprocess_attachment_rag(
    db: Session,
    attachment_id: int,
    current_user_id: int,
) -> RagIngestionJob:
    attachment = ensure_attachment_access(db, current_user_id, attachment_id)
    if attachment.file_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF attachments can be reprocessed",
        )

    reset_attachment_rag_outputs(db, attachment.id)
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
    enqueue_rag_ingestion_job(job)
    return job
