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


class AccessType(str, Enum):
    free = "free"
    paid = "paid"
    subscription = "subscription"
    invite_only = "invite_only"


class AccessConfig(BaseModel):
    access_type: AccessType = AccessType.free
    product_id: Optional[str] = None
    currency: Optional[str] = None
    base_price: Optional[int] = Field(default=None, description="minor units (e.g., cents/paise)")
    discount: Optional[int] = Field(default=None, description="minor units")
    validity_days: Optional[int] = None


class AvailabilityWindow(BaseModel):
    available_from: Optional[datetime] = None
    available_to: Optional[datetime] = None
    regions: List[str] = Field(default_factory=list)


class SeriesCounters(BaseModel):
    total_papers: int = 0
    total_questions: int = 0
    total_duration_mins: int = 0


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
    name: Optional[str] = None  # legacy string name
    title: Optional[Dict[str, str]] = None  # multilingual title
    description: Optional[str] = None  # legacy
    description_i18n: Optional[Dict[str, str]] = None
    target_exam_id: Optional[str] = None  # legacy
    exam_id: Optional[str] = None  # preferred
    series_type: SeriesType
    difficulty_level: SeriesDifficulty = SeriesDifficulty.mixed
    difficulty: Optional[int] = None  # numeric difficulty band
    total_tests: Optional[int] = None
    syllabus_coverage: List[SyllabusCoverageItem] = Field(default_factory=list)
    status: SeriesStatus = SeriesStatus.draft
    is_active: bool = True
    available_from: Optional[datetime] = None  # legacy
    available_until: Optional[datetime] = None  # legacy
    availability: Optional[AvailabilityWindow] = None
    tags: List[str] = Field(default_factory=list)
    language: Optional[str] = "en"  # legacy primary language
    language_codes: List[str] = Field(default_factory=list)
    new_until: Optional[datetime] = None
    published_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    access: Optional[AccessConfig] = None
    counters: Optional[SeriesCounters] = None
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
    title: Optional[Dict[str, str]] = None
    description: Optional[str] = None
    description_i18n: Optional[Dict[str, str]] = None
    exam_id: Optional[str] = None
    target_exam_id: Optional[str] = None
    series_type: Optional[SeriesType] = None
    difficulty_level: Optional[SeriesDifficulty] = None
    difficulty: Optional[int] = None
    total_tests: Optional[int] = None
    syllabus_coverage: Optional[List[SyllabusCoverageItem]] = None
    status: Optional[SeriesStatus] = None
    is_active: Optional[bool] = None
    available_from: Optional[datetime] = None
    available_until: Optional[datetime] = None
    availability: Optional[AvailabilityWindow] = None
    tags: Optional[List[str]] = None
    language: Optional[str] = None
    language_codes: Optional[List[str]] = None
    new_until: Optional[datetime] = None
    published_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    access: Optional[AccessConfig] = None
    counters: Optional[SeriesCounters] = None
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
