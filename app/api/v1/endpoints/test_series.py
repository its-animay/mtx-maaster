from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.db.session import Database, get_db
from app.schemas.test_series import TestSeriesCreate, TestSeriesResponse, TestSeriesUpdate, PaginatedTestSeries
from app.services.test_series_service import (
    create_test_series,
    delete_test_series,
    get_series_stats,
    get_test_series,
    list_test_series,
    update_test_series,
    update_test_series_status,
)
from app.services.test_service import list_tests
from app.schemas.test import PaginatedTests

router = APIRouter()


@router.post("/test-series", response_model=TestSeriesResponse)
def create_test_series_endpoint(payload: TestSeriesCreate, db: Database = Depends(get_db)) -> TestSeriesResponse:
    return create_test_series(payload, db)


@router.get("/test-series", response_model=PaginatedTestSeries)
def list_test_series_endpoint(
    exam_id: Optional[str] = None,
    target_exam_id: Optional[str] = None,
    series_type: Optional[str] = None,
    status: Optional[str] = None,
    is_active: Optional[bool] = None,
    tags: Optional[List[str]] = Query(default=None),
    difficulty: Optional[int] = None,
    language: Optional[str] = None,
    language_code: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "display_order",
    sort_order: str = "asc",
    db: Database = Depends(get_db),
) -> PaginatedTestSeries:
    return list_test_series(
        db=db,
        exam_id=exam_id,
        target_exam_id=target_exam_id,
        series_type=series_type,
        status=status,
        is_active=is_active,
        tags=tags,
        difficulty=difficulty,
        language=language,
        language_code=language_code,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/test-series/{series_id}", response_model=TestSeriesResponse)
def get_test_series_endpoint(series_id: str, db: Database = Depends(get_db)) -> TestSeriesResponse:
    return get_test_series(series_id, db)


@router.put("/test-series/{series_id}", response_model=TestSeriesResponse)
def update_test_series_endpoint(series_id: str, payload: TestSeriesUpdate, db: Database = Depends(get_db)) -> TestSeriesResponse:
    return update_test_series(series_id, payload, db)


@router.patch("/test-series/{series_id}/status", response_model=TestSeriesResponse)
def update_test_series_status_endpoint(series_id: str, status_value: str, db: Database = Depends(get_db)) -> TestSeriesResponse:
    return update_test_series_status(series_id, status_value, db)


@router.delete("/test-series/{series_id}", status_code=204)
def delete_test_series_endpoint(series_id: str, db: Database = Depends(get_db)) -> None:
    delete_test_series(series_id, db)


@router.get("/test-series/{series_id}/stats")
def test_series_stats_endpoint(series_id: str, db: Database = Depends(get_db)) -> dict:
    return get_series_stats(series_id, db)


@router.get("/test-series/{series_id}/tests", response_model=PaginatedTests)
def list_tests_for_series_endpoint(
    series_id: str,
    status: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "test_number",
    sort_order: str = "asc",
    db: Database = Depends(get_db),
) -> PaginatedTests:
    # Exclude heavy questions payload for listing
    return list_tests(
        db=db,
        series_id=series_id,
        status=status,
        is_active=is_active,
        skip=skip,
        limit=limit,
        include_questions=False,
        sort_by=sort_by,
        sort_order=sort_order,
    )
