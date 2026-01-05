from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class OptionSchema(BaseModel):
    """Represents a single option for a question."""

    id: str
    content: str
    rationale: Optional[str] = None


class QuestionType(str, Enum):
    MCQ = "MCQ"  # single correct
    MSQ = "MSQ"  # multiple correct
    NAT = "NAT"  # numeric or short-answer text
    SUBJECTIVE = "SUBJECTIVE"


class QuestionBase(BaseModel):
    """Base fields for question payloads."""

    question_type: QuestionType = QuestionType.MCQ
    subject_id: str
    topic_ids: List[str]
    text: str
    options: List[OptionSchema]
    correct_option_id: Optional[str] = None
    correct_option_ids: Optional[List[str]] = None
    answer_value: Optional[str] = None
    difficulty: int = Field(..., ge=1, le=5, description="1=easy, 5=very hard")
    target_exam_tags: List[str]
    tags: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    version: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    solution: Optional[str] = None
    is_active: bool = True


class QuestionCreate(QuestionBase):
    """Payload to create a question."""

    pass


class QuestionUpdate(BaseModel):
    """Payload to update a question."""

    subject_id: Optional[str] = None
    topic_ids: Optional[List[str]] = None
    text: Optional[str] = None
    options: Optional[List[OptionSchema]] = None
    correct_option_id: Optional[str] = None
    difficulty: Optional[int] = Field(default=None, ge=1, le=5)
    target_exam_tags: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    source: Optional[str] = None
    version: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    solution: Optional[str] = None
    is_active: Optional[bool] = None


class QuestionResponse(QuestionBase):
    """Response model for persisted questions."""

    question_id: str
    created_at: datetime
    updated_at: datetime
