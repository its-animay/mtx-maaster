import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status

from app.db.session import Database, get_db
from app.schemas.exam import ExamCreate, ExamResponse, ExamSyllabusItem, ExamUpdate


def _validate_syllabus(syllabus: List[ExamSyllabusItem], db: Database) -> None:
    """Validate that subjects and topics exist and topics belong to the listed subject."""

    for item in syllabus:
        if not db.get_subject(item.subject_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subject {item.subject_id} does not exist",
            )
        for topic_id in item.topic_ids:
            topic = db.get_topic(topic_id)
            if not topic:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Topic {topic_id} does not exist",
                )
            if topic.subject_id != item.subject_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Topic {topic_id} does not belong to subject {item.subject_id}",
                )


def create_exam(data: ExamCreate, db: Optional[Database] = None) -> ExamResponse:
    """Create an exam ensuring syllabus subjects/topics exist and codes are unique."""

    db = db or get_db()
    _validate_syllabus(data.syllabus, db)

    if db.get_exam_by_code(data.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exam code already exists")

    now = datetime.utcnow()
    exam = ExamResponse(
        exam_id=str(uuid.uuid4()),
        code=data.code,
        name=data.name,
        description=data.description,
        syllabus=data.syllabus,
        version=data.version,
        is_active=data.is_active,
        metadata=data.metadata,
        created_by=data.created_by,
        created_at=now,
        updated_at=now,
    )
    db.insert_exam(exam)
    return exam


def get_exam(exam_id: str, db: Optional[Database] = None) -> ExamResponse:
    """Fetch an exam by id or raise 404."""

    db = db or get_db()
    exam = db.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    return exam


def list_exams(db: Optional[Database] = None, active_only: bool = False) -> List[ExamResponse]:
    """Return exams optionally filtered by active status."""

    db = db or get_db()
    return db.list_exams(active_only=active_only)


def update_exam(exam_id: str, payload: ExamUpdate, db: Optional[Database] = None) -> ExamResponse:
    """Update exam details and syllabus after validation."""

    db = db or get_db()
    exam = get_exam(exam_id, db)

    if payload.code and payload.code != exam.code:
        existing = db.get_exam_by_code(payload.code)
        if existing and existing.exam_id != exam_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exam code already exists")

    if payload.syllabus is not None:
        _validate_syllabus(payload.syllabus, db)

    updated = exam.copy(update={k: v for k, v in payload.dict(exclude_unset=True).items()})
    updated.updated_at = datetime.utcnow()
    db.update_exam(updated)
    return updated


def delete_exam(exam_id: str, db: Optional[Database] = None) -> None:
    """Delete an exam or raise 404 if missing."""

    db = db or get_db()
    if not db.get_exam(exam_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    db.delete_exam(exam_id)


def get_exam_syllabus(exam_id: str, db: Optional[Database] = None) -> List[ExamSyllabusItem]:
    """Return only the syllabus section for an exam."""

    exam = get_exam(exam_id, db)
    return exam.syllabus
