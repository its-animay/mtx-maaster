from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, constr


SlugStr = constr(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class SeriesStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class SeriesType(str, Enum):
    full_length_mock = "full_length_mock"
    chapter_wise = "chapter_wise"
    topic_wise = "topic_wise"
    previous_year = "previous_year"
    subject_wise = "subject_wise"
    revision = "revision"
    mixed = "mixed"


class SeriesDifficulty(str, Enum):
    easy = "easy"
    intermediate = "intermediate"
    advanced = "advanced"
    mixed = "mixed"


class SyllabusCoverageItem(BaseModel):
    """Defines subject/topic coverage for a series."""

    subject_id: str
    topic_ids: List[str] = Field(default_factory=list)
    weightage: Optional[float] = Field(default=None, ge=0, le=1)


class SeriesStats(BaseModel):
    """Aggregated metrics for a test series."""

    total_tests: Optional[int] = None
    total_questions: Optional[int] = None
    avg_difficulty: Optional[float] = None
    total_duration_minutes: Optional[int] = None


class TestSeriesBase(BaseModel):
    """Base fields for test series DTOs."""

    code: str
    slug: SlugStr
    name: str
    description: Optional[str] = None
    target_exam_id: str
    series_type: SeriesType
    difficulty_level: SeriesDifficulty = SeriesDifficulty.mixed
    total_tests: Optional[int] = None
    syllabus_coverage: List[SyllabusCoverageItem] = Field(default_factory=list)
    status: SeriesStatus = SeriesStatus.draft
    is_active: bool = True
    available_from: Optional[datetime] = None
    available_until: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    language: Optional[str] = "en"
    version: Optional[str] = None
    display_order: int = 0
    stats: Optional[SeriesStats] = None
    metadata: Optional[Dict[str, Any]] = None


class TestSeriesCreate(TestSeriesBase):
    """Payload to create a test series."""

    pass


class TestSeriesUpdate(BaseModel):
    """Payload to update a test series."""

    name: Optional[str] = None
    description: Optional[str] = None
    series_type: Optional[SeriesType] = None
    difficulty_level: Optional[SeriesDifficulty] = None
    total_tests: Optional[int] = None
    syllabus_coverage: Optional[List[SyllabusCoverageItem]] = None
    status: Optional[SeriesStatus] = None
    is_active: Optional[bool] = None
    available_from: Optional[datetime] = None
    available_until: Optional[datetime] = None
    tags: Optional[List[str]] = None
    language: Optional[str] = None
    version: Optional[str] = None
    display_order: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class TestSeriesResponse(TestSeriesBase):
    """Response model for persisted test series."""

    series_id: str
    created_at: datetime
    updated_at: datetime


class PaginatedTestSeries(BaseModel):
    """Envelope for paginated test series listings."""

    items: List[TestSeriesResponse]
    total: int
    skip: int
    limit: int
