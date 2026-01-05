import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status

from app.db.session import Database, get_db
from app.schemas.master import (
    PaginatedSubjects,
    SubjectCreate,
    SubjectResponse,
    SubjectUpdate,
    TopicCreate,
    TopicResponse,
    TopicUpdate,
)


def create_subject(subject: SubjectCreate, db: Optional[Database] = None) -> SubjectResponse:
    """Create a subject with slug uniqueness and timestamps."""

    db = db or get_db()
    subject_id = subject.id or f"subject_{uuid.uuid4()}"
    if db.get_subject(subject_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject id already exists")
    if db.get_subject_by_slug(subject.slug):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject slug already exists")

    now = datetime.utcnow()
    created = SubjectResponse(
        id=subject_id,
        name=subject.name,
        slug=subject.slug,
        description=subject.description,
        tags=subject.tags,
        metadata=subject.metadata,
        is_active=subject.is_active,
        created_at=now,
        updated_at=now,
    )
    db.insert_subject(created)
    return created


def get_subject(subject_id: str, db: Optional[Database] = None) -> SubjectResponse:
    """Fetch a subject or raise 404."""

    db = db or get_db()
    subject = db.get_subject(subject_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    return subject


def list_subjects(
    db: Optional[Database] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    tags: Optional[List[str]] = None,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "name",
    sort_order: str = "asc",
) -> PaginatedSubjects:
    """Return subjects with filters and pagination."""

    db = db or get_db()
    items, total = db.list_subjects(
        is_active=is_active,
        search=search,
        tags=tags,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        include_total=True,
    )
    return PaginatedSubjects(items=items, total=total, skip=skip, limit=limit)


def update_subject(subject_id: str, payload: SubjectUpdate, db: Optional[Database] = None) -> SubjectResponse:
    """Update a subject's metadata and status."""

    db = db or get_db()
    subject = get_subject(subject_id, db)

    if payload.slug and payload.slug != subject.slug:
        existing = db.get_subject_by_slug(payload.slug)
        if existing and existing.id != subject_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject slug already exists")

    updated = subject.copy(update={k: v for k, v in payload.dict(exclude_unset=True).items()})
    updated.updated_at = datetime.utcnow()
    db.update_subject(updated)
    return updated


def delete_subject(subject_id: str, db: Optional[Database] = None) -> None:
    """Remove a subject. Prevent deletion if topics exist under it."""

    db = db or get_db()
    if not db.get_subject(subject_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    if any(topic.subject_id == subject_id for topic in db.list_topics()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete subject with existing topics. Delete topics first.",
        )
    db.delete_subject(subject_id)


def _validate_topic_references(topic: TopicResponse, db: Database, ref_ids: List[str]) -> None:
    """Ensure referenced topics exist within the same subject."""

    for ref_id in ref_ids:
        ref_topic = db.get_topic(ref_id)
        if not ref_topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Referenced topic {ref_id} not found"
            )
        if ref_topic.subject_id != topic.subject_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Topic {ref_id} does not belong to subject {topic.subject_id}",
                )


def create_topic(topic: TopicCreate, db: Optional[Database] = None) -> TopicResponse:
    """Create a topic ensuring subject exists and slug uniqueness per subject."""

    db = db or get_db()
    if not db.get_subject(topic.subject_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    topic_id = topic.id or f"topic_{uuid.uuid4()}"
    if db.get_topic(topic_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Topic id already exists")
    if db.get_topic_by_slug(topic.subject_id, topic.slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Topic slug already exists for this subject"
        )

    now = datetime.utcnow()
    created = TopicResponse(
        id=topic_id,
        subject_id=topic.subject_id,
        name=topic.name,
        slug=topic.slug,
        description=topic.description,
        difficulty_weight=topic.difficulty_weight,
        bloom_level=topic.bloom_level,
        related_topic_ids=topic.related_topic_ids,
        prerequisite_topic_ids=topic.prerequisite_topic_ids,
        tags=topic.tags,
        metadata=topic.metadata,
        is_active=topic.is_active,
        created_at=now,
        updated_at=now,
    )
    _validate_topic_references(created, db, created.related_topic_ids)
    _validate_topic_references(created, db, created.prerequisite_topic_ids)

    db.insert_topic(created)
    return created


def get_topic(topic_id: str, db: Optional[Database] = None) -> TopicResponse:
    """Fetch a topic by id or raise 404."""

    db = db or get_db()
    topic = db.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return topic


def list_topics(subject_id: Optional[str] = None, db: Optional[Database] = None) -> List[TopicResponse]:
    """List topics optionally filtered by subject id."""

    db = db or get_db()
    return db.list_topics(subject_id)


def update_topic(topic_id: str, payload: TopicUpdate, db: Optional[Database] = None) -> TopicResponse:
    """Update topic details, relationships, and status."""

    db = db or get_db()
    topic = get_topic(topic_id, db)

    if payload.slug and payload.slug != topic.slug:
        existing = db.get_topic_by_slug(topic.subject_id, payload.slug)
        if existing and existing.id != topic.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Topic slug already exists for this subject"
            )
    if payload.subject_id and payload.subject_id != topic.subject_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Changing subject of a topic is not allowed"
        )

    updated = topic.copy(update={k: v for k, v in payload.dict(exclude_unset=True).items()})
    if updated.related_topic_ids is None:
        updated.related_topic_ids = []
    if updated.prerequisite_topic_ids is None:
        updated.prerequisite_topic_ids = []
    _validate_topic_references(updated, db, updated.related_topic_ids)
    _validate_topic_references(updated, db, updated.prerequisite_topic_ids)
    updated.updated_at = datetime.utcnow()

    db.update_topic(updated)
    return updated


def delete_topic(topic_id: str, db: Optional[Database] = None) -> None:
    """Delete a topic or raise 404."""

    db = db or get_db()
    if not db.get_topic(topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    db.delete_topic(topic_id)


def update_topic_links(
    topic_id: str,
    related_topic_ids: Optional[List[str]] = None,
    prerequisite_topic_ids: Optional[List[str]] = None,
    db: Optional[Database] = None,
) -> TopicResponse:
    """Update only the relationship graph for a topic."""

    payload = TopicUpdate(
        related_topic_ids=related_topic_ids,
        prerequisite_topic_ids=prerequisite_topic_ids,
    )
    return update_topic(topic_id, payload, db)
