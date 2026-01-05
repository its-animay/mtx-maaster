from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QuestionDocType(str, Enum):
    single_choice = "single_choice"
    multi_choice = "multi_choice"
    integer = "integer"
    short_text = "short_text"
    true_false = "true_false"


class AnswerKeyType(str, Enum):
    single = "single"
    multi = "multi"
    value = "value"


class OptionDoc(BaseModel):
    id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


class AnswerKey(BaseModel):
    type: AnswerKeyType
    option_id: Optional[str] = None
    option_ids: Optional[List[str]] = None
    value: Optional[str] = None


class SolutionDoc(BaseModel):
    explanation: Optional[str] = None
    steps: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)


class TaxonomyDoc(BaseModel):
    subject_id: Optional[str] = None
    topic_ids: List[str] = Field(default_factory=list)
    target_exam_ids: List[str] = Field(default_factory=list)


class UsageStatus(str, Enum):
    draft = "draft"
    published = "published"


class Visibility(str, Enum):
    public = "public"
    private = "private"


class UsageDoc(BaseModel):
    status: UsageStatus = UsageStatus.draft
    is_active: bool = True
    visibility: Visibility = Visibility.public


class MetaDoc(BaseModel):
    estimated_time_sec: Optional[int] = Field(default=None, ge=0)
    source: Optional[str] = None
    created_by: Optional[str] = None


class QuestionDocBase(BaseModel):
    text: str = Field(..., min_length=1)
    type: QuestionDocType
    options: List[OptionDoc] = Field(default_factory=list)
    answer_key: AnswerKey
    solution: Optional[SolutionDoc] = None
    taxonomy: TaxonomyDoc
    difficulty: int = Field(..., ge=1, le=5)
    tags: List[str] = Field(default_factory=list)
    language: str = "en"
    usage: UsageDoc = Field(default_factory=UsageDoc)
    meta: MetaDoc = Field(default_factory=MetaDoc)

    @model_validator(mode="after")
    def validate_type_specific(self) -> "QuestionDocBase":
        # If answer_key is missing (e.g., projected out in a public view), skip validation.
        if self.answer_key is None:
            return self

        qtype = self.type
        options = self.options or []
        opt_ids = {opt.id for opt in options}

        if qtype in (QuestionDocType.single_choice, QuestionDocType.multi_choice, QuestionDocType.true_false):
            if not options and qtype != QuestionDocType.true_false:
                raise ValueError("options are required for choice questions")
            if self.answer_key.type == AnswerKeyType.single:
                if not self.answer_key.option_id:
                    raise ValueError("answer_key.option_id is required for single answer")
                if opt_ids and self.answer_key.option_id not in opt_ids:
                    raise ValueError("answer_key.option_id must exist in options")
            elif self.answer_key.type == AnswerKeyType.multi:
                if not self.answer_key.option_ids:
                    raise ValueError("answer_key.option_ids is required for multi answer")
                missing = [oid for oid in self.answer_key.option_ids if oid not in opt_ids]
                if missing:
                    raise ValueError(f"answer_key.option_ids missing in options: {missing}")
            else:
                raise ValueError("choice questions must use answer_key.type=single|multi")

        if qtype in (QuestionDocType.integer, QuestionDocType.short_text):
            if options:
                raise ValueError("options must be empty for value questions")
            if self.answer_key.type != AnswerKeyType.value:
                raise ValueError("value questions require answer_key.type=value")
            if not self.answer_key.value:
                raise ValueError("answer_key.value is required for value questions")

        return self


class QuestionDocCreate(QuestionDocBase):
    """Payload to create a question document."""


class QuestionDocUpdate(BaseModel):
    text: Optional[str] = None
    type: Optional[QuestionDocType] = None
    options: Optional[List[OptionDoc]] = None
    answer_key: Optional[AnswerKey] = None
    solution: Optional[SolutionDoc] = None
    taxonomy: Optional[TaxonomyDoc] = None
    difficulty: Optional[int] = Field(default=None, ge=1, le=5)
    tags: Optional[List[str]] = None
    language: Optional[str] = None
    usage: Optional[UsageDoc] = None
    meta: Optional[MetaDoc] = None


class QuestionDocResponse(QuestionDocBase):
    answer_key: Optional[AnswerKey] = None
    solution: Optional[SolutionDoc] = None
    question_id: str
    version: int
    search_blob: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    rand_key: Optional[float] = None
    schema_version: Optional[int] = None
    model_config = ConfigDict(extra="ignore")


class QuestionPublicView(QuestionDocResponse):
    model_config = ConfigDict(
        fields={
            "answer_key": {"exclude": True},
            "solution": {"exclude": True},
            "search_blob": {"exclude": True},
            "rand_key": {"exclude": True},
            "schema_version": {"exclude": True},
        },
        extra="ignore",
    )


class QuestionPreviewView(QuestionDocResponse):
    model_config = ConfigDict(
        fields={
            "solution": {"exclude": True},
            "search_blob": {"exclude": True},
            "rand_key": {"exclude": True},
            "schema_version": {"exclude": True},
        },
        extra="ignore",
    )


class QuestionFullView(QuestionDocResponse):
    model_config = ConfigDict(
        fields={
            "search_blob": {"exclude": True},
            "rand_key": {"exclude": True},
            "schema_version": {"exclude": True},
        },
        extra="ignore",
    )


class PaginatedQuestions(BaseModel):
    items: List[QuestionPublicView]
    total: int
    skip: int
    limit: int
