from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SubjectBase(BaseModel):
    """Base fields shared across Subject DTOs."""

    name: str
    slug: str = Field(..., min_length=2, description="URL-friendly unique slug for the subject")
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
    is_active: bool = True


class SubjectCreate(SubjectBase):
    """Payload to create a subject."""

    id: Optional[str] = None


class SubjectUpdate(BaseModel):
    """Payload to update a subject."""

    name: Optional[str] = None
    slug: Optional[str] = Field(default=None, min_length=2)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class SubjectResponse(SubjectBase):
    """Representation of a persisted subject."""

    id: str
    created_at: datetime
    updated_at: datetime


class PaginatedSubjects(BaseModel):
    """Envelope for paginated subject listings."""

    items: List[SubjectResponse]
    total: int
    skip: int
    limit: int


class TopicBase(BaseModel):
    """Base fields shared across Topic DTOs."""

    subject_id: str
    name: str
    slug: str = Field(..., min_length=2)
    description: Optional[str] = None
    difficulty_weight: float = Field(..., ge=0, le=1)
    bloom_level: Optional[str] = Field(
        default=None, description="Bloom taxonomy level (e.g. Remember, Apply, Analyze)"
    )
    related_topic_ids: List[str] = Field(default_factory=list)
    prerequisite_topic_ids: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
    is_active: bool = True


class TopicCreate(TopicBase):
    """Payload to create a topic."""

    id: Optional[str] = None


class TopicUpdate(BaseModel):
    """Payload to update a topic."""

    subject_id: Optional[str] = None
    name: Optional[str] = None
    slug: Optional[str] = Field(default=None, min_length=2)
    description: Optional[str] = None
    difficulty_weight: Optional[float] = Field(default=None, ge=0, le=1)
    bloom_level: Optional[str] = None
    related_topic_ids: Optional[List[str]] = None
    prerequisite_topic_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class TopicResponse(TopicBase):
    """Representation of a persisted topic."""

    id: str
    created_at: datetime
    updated_at: datetime


class TopicUpdateLinks(BaseModel):
    """Payload to update topic relationships."""

    related_topic_ids: Optional[List[str]] = None
    prerequisite_topic_ids: Optional[List[str]] = None
