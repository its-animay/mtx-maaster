from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExamSyllabusItem(BaseModel):
    """Defines a subject and its included topics for an exam syllabus."""

    subject_id: str
    topic_ids: List[str]
    weight: Optional[float] = Field(
        default=None, ge=0, le=1, description="Optional weight to prioritize the subject within the exam"
    )


class ExamBase(BaseModel):
    """Base fields shared across Exam DTOs."""

    code: str
    name: str
    description: Optional[str] = None
    syllabus: List[ExamSyllabusItem]
    version: Optional[str] = None
    is_active: bool = True
    metadata: Optional[Dict[str, Any]] = None


class ExamCreate(ExamBase):
    """Payload to create an exam."""

    created_by: Optional[str] = None


class ExamUpdate(BaseModel):
    """Payload to update an exam."""

    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    syllabus: Optional[List[ExamSyllabusItem]] = None
    version: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class ExamResponse(ExamBase):
    """Response model for persisted exams."""

    exam_id: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
