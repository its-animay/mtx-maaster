from typing import List, Optional

from fastapi import APIRouter, Depends

from app.db.session import Database, get_db
from app.schemas.test import (
    AddQuestionsRequest,
    BulkAddRequest,
    PaginatedTests,
    QuestionReference,
    ReplaceQuestionRequest,
    ReorderRequest,
    TestCreate,
    TestResponse,
    TestUpdate,
    UpdateMarksRequest,
    ValidationResult,
    TestStats,
)
from app.services.test_service import (
    add_questions_to_test,
    bulk_add_questions,
    create_test,
    delete_test,
    get_answer_key,
    get_test,
    get_test_preview,
    get_test_with_solutions,
    list_tests,
    remove_question,
    reorder_questions,
    replace_question,
    test_stats,
    update_question_marks,
    update_test,
    validate_test,
)

router = APIRouter()


@router.post("/tests", response_model=TestResponse)
def create_test_endpoint(payload: TestCreate, db: Database = Depends(get_db)) -> TestResponse:
    return create_test(payload, db)


@router.get("/tests/{test_id}", response_model=TestResponse)
def get_test_endpoint(test_id: str, db: Database = Depends(get_db)) -> TestResponse:
    return get_test(test_id, db)


@router.put("/tests/{test_id}", response_model=TestResponse)
def update_test_endpoint(test_id: str, payload: TestUpdate, db: Database = Depends(get_db)) -> TestResponse:
    return update_test(test_id, payload, db)


@router.delete("/tests/{test_id}")
def delete_test_endpoint(test_id: str, db: Database = Depends(get_db)) -> dict:
    delete_test(test_id, db)
    return {"status": "deleted", "test_id": test_id}


@router.get("/tests", response_model=PaginatedTests)
def list_tests_endpoint(
    series_id: Optional[str] = None,
    status: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "test_number",
    sort_order: str = "asc",
    db: Database = Depends(get_db),
) -> PaginatedTests:
    return list_tests(
        db=db,
        series_id=series_id,
        status=status,
        is_active=is_active,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("/tests/{test_id}/questions", response_model=List[QuestionReference])
def add_questions_endpoint(test_id: str, payload: AddQuestionsRequest, db: Database = Depends(get_db)) -> List[QuestionReference]:
    return add_questions_to_test(test_id, payload, db)


@router.post("/tests/{test_id}/questions/bulk-add", response_model=List[QuestionReference])
def bulk_add_questions_endpoint(test_id: str, payload: BulkAddRequest, db: Database = Depends(get_db)) -> List[QuestionReference]:
    return bulk_add_questions(test_id, payload, db)


@router.delete("/tests/{test_id}/questions/{question_id}")
def remove_question_endpoint(test_id: str, question_id: str, db: Database = Depends(get_db)) -> dict:
    remove_question(test_id, question_id, db)
    return {"status": "deleted", "question_id": question_id}


@router.patch("/tests/{test_id}/questions/reorder", response_model=List[QuestionReference])
def reorder_questions_endpoint(test_id: str, payload: ReorderRequest, db: Database = Depends(get_db)) -> List[QuestionReference]:
    return reorder_questions(test_id, payload, db)


@router.put("/tests/{test_id}/questions/{old_question_id}/replace", response_model=QuestionReference)
def replace_question_endpoint(
    test_id: str,
    old_question_id: str,
    payload: ReplaceQuestionRequest,
    db: Database = Depends(get_db),
) -> QuestionReference:
    return replace_question(test_id, old_question_id, payload, db)


@router.patch("/tests/{test_id}/questions/{question_id}/marks", response_model=QuestionReference)
def update_question_marks_endpoint(
    test_id: str, question_id: str, payload: UpdateMarksRequest, db: Database = Depends(get_db)
) -> QuestionReference:
    return update_question_marks(test_id, question_id, payload, db)


@router.get("/tests/{test_id}/preview")
def test_preview_endpoint(test_id: str, db: Database = Depends(get_db)) -> dict:
    return get_test_preview(test_id, db)


@router.get("/tests/{test_id}/with-solutions")
def test_with_solutions_endpoint(test_id: str, db: Database = Depends(get_db)) -> dict:
    return get_test_with_solutions(test_id, db)


@router.get("/tests/{test_id}/answer-key")
def answer_key_endpoint(test_id: str, db: Database = Depends(get_db)) -> dict:
    return get_answer_key(test_id, db)


@router.get("/tests/{test_id}/validate", response_model=ValidationResult)
def validate_test_endpoint(test_id: str, db: Database = Depends(get_db)) -> ValidationResult:
    return validate_test(test_id, db)


@router.get("/tests/{test_id}/stats", response_model=TestStats)
def test_stats_endpoint(test_id: str, db: Database = Depends(get_db)) -> TestStats:
    return test_stats(test_id, db)
