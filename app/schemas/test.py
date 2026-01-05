from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, constr

from app.schemas.question import QuestionType
from app.schemas.test_series import SlugStr


class TestStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class ReleaseMode(str, Enum):
    after_submission = "after_submission"
    scheduled = "scheduled"
    manual = "manual"
    never = "never"


class AvailabilityMode(str, Enum):
    always = "always"
    scheduled = "scheduled"
    date_range = "date_range"


class SectionMarkingScheme(BaseModel):
    """Marks configuration per question type."""

    correct: float
    incorrect: float = 0.0
    unattempted: float = 0.0
    partial: Optional[float] = None


class TestSection(BaseModel):
    """Defines a section within a test."""

    section_id: str
    section_code: str
    name: str
    display_order: int
    subject_id: str
    total_questions: int
    total_marks: Optional[float] = None
    duration_minutes: Optional[int] = None
    can_switch_section: bool = True
    is_optional: bool = False
    marking_scheme: Dict[QuestionType, SectionMarkingScheme]


class TestPattern(BaseModel):
    """Test level pattern and section configuration."""

    total_duration_minutes: int
    total_marks: Optional[float] = None
    total_questions: int
    sections: List[TestSection]


class QuestionReference(BaseModel):
    """Reference-only question mapping stored inside a test."""

    seq: int
    section_id: str
    question_id: str
    question_type: QuestionType
    subject_id: str
    topic_ids: List[str]
    difficulty: int
    marks: Optional[float] = None
    negative_marks: Optional[float] = None
    is_bonus: bool = False
    is_optional: bool = False


class AddQuestionsRequest(BaseModel):
    """Request payload to add specific questions to a test section."""

    section_id: str
    question_ids: List[str]
    starting_seq: Optional[int] = None
    marks: Optional[float] = None
    negative_marks: Optional[float] = None
    is_bonus: bool = False
    is_optional: bool = False


class BulkCriteria(BaseModel):
    """Criteria used to select questions for bulk add."""

    subject_id: str
    topic_ids: Optional[List[str]] = None
    difficulty: Optional[List[int]] = None
    question_types: Optional[List[QuestionType]] = None


class BulkAddRequest(BaseModel):
    """Request payload for criteria-based bulk add."""

    section_id: str
    criteria: BulkCriteria
    count: int
    strategy: str = Field(default="random", description="random|difficulty_sorted|sequential")
    starting_seq: Optional[int] = None


class ReorderRequest(BaseModel):
    """Request payload to reorder questions within a section."""

    section_id: str
    question_sequence: List[Dict[str, int]]


class ReplaceQuestionRequest(BaseModel):
    """Payload to replace a question in a test."""

    new_question_id: str
    preserve_sequence: bool = True


class UpdateMarksRequest(BaseModel):
    """Payload to update marks for a specific question."""

    marks: Optional[float] = None
    negative_marks: Optional[float] = None
    is_bonus: Optional[bool] = None
    is_optional: Optional[bool] = None


class TestSettings(BaseModel):
    """UI/attempt settings."""

    shuffle_questions: bool = False
    shuffle_options: bool = False
    shuffle_sections: bool = False
    show_calculator: bool = False
    show_question_palette: bool = True
    allow_section_navigation: bool = True


class SolutionsConfig(BaseModel):
    """Controls solution/answer release."""

    has_solutions: bool = True
    release_mode: ReleaseMode = ReleaseMode.after_submission
    release_at: Optional[datetime] = None
    pdf_url: Optional[str] = None
    video_url: Optional[str] = None


class Availability(BaseModel):
    """Availability window for attempting a test."""

    mode: AvailabilityMode = AvailabilityMode.always
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class TestBase(BaseModel):
    """Base fields for tests."""

    code: str
    slug: SlugStr
    series_id: Optional[str] = None
    test_number: Optional[int] = None
    name: str
    description: Optional[str] = None
    pattern: TestPattern
    settings: TestSettings = Field(default_factory=TestSettings)
    solutions: SolutionsConfig = Field(default_factory=SolutionsConfig)
    availability: Availability = Field(default_factory=Availability)
    is_active: bool = True
    status: TestStatus = TestStatus.draft
    tags: List[str] = Field(default_factory=list)
    version: Optional[str] = None
    language: Optional[str] = "en"
    metadata: Optional[Dict[str, Any]] = None


class TestCreate(TestBase):
    """Payload to create a test."""

    questions: List[QuestionReference] = Field(default_factory=list)


class TestUpdate(BaseModel):
    """Payload to update test metadata (not questions)."""

    name: Optional[str] = None
    description: Optional[str] = None
    pattern: Optional[TestPattern] = None
    settings: Optional[TestSettings] = None
    solutions: Optional[SolutionsConfig] = None
    availability: Optional[Availability] = None
    is_active: Optional[bool] = None
    status: Optional[TestStatus] = None
    tags: Optional[List[str]] = None
    version: Optional[str] = None
    language: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TestResponse(TestBase):
    """Response model for persisted tests."""

    test_id: str
    questions: List[QuestionReference] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PaginatedTests(BaseModel):
    """Envelope for paginated test listings."""

    items: List[TestResponse]
    total: int
    skip: int
    limit: int


class ValidationResult(BaseModel):
    """Validation result for a test."""

    is_valid: bool
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class TestStats(BaseModel):
    """Aggregated stats for a test."""

    difficulty_distribution: Dict[int, int]
    type_distribution: Dict[QuestionType, int]
    topic_coverage: Dict[str, int]
    section_stats: Dict[str, Dict[str, int]]
