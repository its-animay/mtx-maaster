from typing import List, Optional

from fastapi import APIRouter, Query

from app.schemas.question_doc import (
    PaginatedQuestions,
    QuestionDocCreate,
    QuestionDocUpdate,
    QuestionFullView,
    QuestionPreviewView,
    QuestionPublicView,
)
from app.services.question_service import discover_questions, get_question, sample_questions, create_question, update_question

router = APIRouter()


@router.post("/questions", response_model=QuestionFullView, status_code=201)
def create_question_endpoint(payload: QuestionDocCreate) -> QuestionFullView:
    return create_question(payload)


@router.patch("/questions/{question_id}", response_model=QuestionFullView)
def update_question_endpoint(question_id: str, payload: QuestionDocUpdate) -> QuestionFullView:
    return update_question(question_id, payload)


@router.get(
    "/questions/{question_id}",
    response_model=QuestionFullView | QuestionPreviewView | QuestionPublicView,
    response_model_exclude_none=True,
)
def get_question_endpoint(
    question_id: str,
    include_solution: bool = False,
    include_answer_key: bool = False,
) -> QuestionPublicView | QuestionPreviewView | QuestionFullView:
    return get_question(question_id, include_solution=include_solution, include_answer_key=include_answer_key)


@router.get("/list/questions/discover", response_model=PaginatedQuestions, response_model_exclude_none=True)
def discover_questions_endpoint(
    subject_id: Optional[str] = None,
    topic_ids: Optional[List[str]] = Query(default=None),
    target_exam_ids: Optional[List[str]] = Query(default=None),
    difficulty_min: Optional[int] = None,
    difficulty_max: Optional[int] = None,
    tags: Optional[List[str]] = Query(default=None),
    status_value: Optional[str] = "published",
    is_active: Optional[bool] = True,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> PaginatedQuestions:
    return discover_questions(
        subject_id=subject_id,
        topic_ids=topic_ids,
        target_exam_ids=target_exam_ids,
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        tags=tags,
        status_value=status_value,
        is_active=is_active,
        search=search,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/questions/list", response_model=PaginatedQuestions, response_model_exclude_none=True)
def list_questions_endpoint(
    subject_id: Optional[str] = None,
    topic_ids: Optional[List[str]] = Query(default=None),
    target_exam_ids: Optional[List[str]] = Query(default=None),
    difficulty_min: Optional[int] = None,
    difficulty_max: Optional[int] = None,
    tags: Optional[List[str]] = Query(default=None),
    status_value: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> PaginatedQuestions:
    """
    List questions with full filtering and pagination.

    If no filters are provided, returns all schema_version=2 questions with the chosen sort and pagination.
    """

    return discover_questions(
        subject_id=subject_id,
        topic_ids=topic_ids,
        target_exam_ids=target_exam_ids,
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        tags=tags,
        status_value=status_value,
        is_active=is_active,
        search=search,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/questions/sample", response_model=List[QuestionPublicView], response_model_exclude_none=True)
def sample_questions_endpoint(
    subject_id: Optional[str] = None,
    topic_ids: Optional[List[str]] = Query(default=None),
    target_exam_ids: Optional[List[str]] = Query(default=None),
    difficulty_min: Optional[int] = None,
    difficulty_max: Optional[int] = None,
    tags: Optional[List[str]] = Query(default=None),
    status_value: Optional[str] = "published",
    is_active: Optional[bool] = True,
    limit: int = 1,
    seed: Optional[str] = None,
) -> List[QuestionPublicView]:
    return sample_questions(
        subject_id=subject_id,
        topic_ids=topic_ids,
        target_exam_ids=target_exam_ids,
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        tags=tags,
        status_value=status_value,
        is_active=is_active,
        limit=limit,
        seed=seed,
    )
