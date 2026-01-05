import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status

from app.db.session import Database, get_db
from app.schemas.test_series import (
    PaginatedTestSeries,
    SeriesStatus,
    SyllabusCoverageItem,
    TestSeriesCreate,
    TestSeriesResponse,
    TestSeriesUpdate,
)


def _validate_syllabus_coverage(items: List[SyllabusCoverageItem], db: Database) -> None:
    for item in items:
        subject = db.get_subject(item.subject_id)
        if not subject:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Subject {item.subject_id} not found")
        for topic_id in item.topic_ids:
            topic = db.get_topic(topic_id)
            if not topic:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Topic {topic_id} not found")
            if topic.subject_id != item.subject_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Topic {topic_id} does not belong to subject {item.subject_id}",
                )


def create_test_series(data: TestSeriesCreate, db: Optional[Database] = None) -> TestSeriesResponse:
    db = db or get_db()

    if db.get_test_series_by_code(data.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Series code already exists")
    if db.get_test_series_by_slug(data.slug):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Series slug already exists")

    if not db.get_exam_by_code(data.target_exam_id) and not db.get_exam(data.target_exam_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target exam not found")

    _validate_syllabus_coverage(data.syllabus_coverage, db)

    now = datetime.utcnow()
    series = TestSeriesResponse(
        series_id=f"ts_{uuid.uuid4()}",
        created_at=now,
        updated_at=now,
        **data.model_dump(),
    )
    db.insert_test_series(series)
    return series


def get_test_series(series_id: str, db: Optional[Database] = None) -> TestSeriesResponse:
    db = db or get_db()
    series = db.get_test_series(series_id)
    if not series:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test series not found")
    return series


def list_test_series(
    db: Optional[Database] = None,
    target_exam_id: Optional[str] = None,
    series_type: Optional[str] = None,
    status: Optional[str] = None,
    is_active: Optional[bool] = None,
    tags: Optional[List[str]] = None,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "display_order",
    sort_order: str = "asc",
) -> PaginatedTestSeries:
    db = db or get_db()
    items, total = db.list_test_series(
        target_exam_id=target_exam_id,
        series_type=series_type,
        status=status,
        is_active=is_active,
        tags=tags,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        include_total=True,
    )
    return PaginatedTestSeries(items=items, total=total, skip=skip, limit=limit)


def update_test_series(series_id: str, payload: TestSeriesUpdate, db: Optional[Database] = None) -> TestSeriesResponse:
    db = db or get_db()
    existing = get_test_series(series_id, db)

    update_data = payload.model_dump(exclude_unset=True)
    if "code" in update_data or "target_exam_id" in update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot modify code or target_exam_id")

    merged = existing.copy(update=update_data)

    if merged.syllabus_coverage:
        _validate_syllabus_coverage(merged.syllabus_coverage, db)

    merged.updated_at = datetime.utcnow()
    db.update_test_series(merged)
    return merged


def update_test_series_status(series_id: str, status_value: str, db: Optional[Database] = None) -> TestSeriesResponse:
    db = db or get_db()
    existing = get_test_series(series_id, db)
    try:
        existing.status = SeriesStatus(status_value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status value")
    existing.updated_at = datetime.utcnow()
    db.update_test_series(existing)
    return existing


def delete_test_series(series_id: str, db: Optional[Database] = None) -> None:
    db = db or get_db()
    existing = get_test_series(series_id, db)
    if db.count_tests_for_series(series_id) > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete series with existing tests"
        )
    db.delete_test_series(existing.series_id)


def get_series_stats(series_id: str, db: Optional[Database] = None) -> dict:
    db = db or get_db()
    get_test_series(series_id, db)
    stats = db.aggregate_series_stats(series_id)
    return stats or {"total_tests": 0, "total_questions": 0, "avg_difficulty": None, "total_duration_minutes": 0}
