import random
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status

from app.db.questions_repo import QuestionRepo, get_question_repo
from app.schemas.question_doc import (
    AnswerKey,
    AnswerKeyType,
    PaginatedQuestions,
    QuestionDocCreate,
    QuestionDocResponse,
    QuestionDocType,
    QuestionDocUpdate,
    QuestionFullView,
    QuestionPublicView,
    QuestionPreviewView,
    UsageStatus,
)

SCHEMA_VERSION = 2

# Projection helpers
PUBLIC_PROJECTION = {
    "search_blob": 0,
    "rand_key": 0,
}
PREVIEW_PROJECTION = {
    "search_blob": 0,
    "rand_key": 0,
    "solution": 0,
}
FULL_PROJECTION = {
    "search_blob": 0,
    "rand_key": 0,
}


def _build_search_blob(payload: dict) -> str:
    """Create a normalized blob for text search."""

    parts: List[str] = []
    parts.append(payload.get("text", ""))
    for opt in payload.get("options", []):
        parts.append(opt.get("text", ""))
    parts.extend(payload.get("tags", []))
    taxonomy = payload.get("taxonomy", {})
    parts.append(taxonomy.get("subject_id") or "")
    parts.extend(taxonomy.get("topic_ids", []))
    parts.extend(taxonomy.get("target_exam_ids", []))
    blob = " ".join(parts)
    return " ".join(blob.lower().split())


def _validate_answer_key(question_type: QuestionDocType, answer_key: AnswerKey, options: List[Dict]) -> None:
    opt_ids = {opt["id"] for opt in options}

    if question_type in (QuestionDocType.single_choice, QuestionDocType.true_false):
        if question_type == QuestionDocType.single_choice and not options:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="options are required for single_choice")
        if answer_key.type != AnswerKeyType.single:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="single_choice requires answer_key.type=single")
        if not answer_key.option_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="answer_key.option_id is required")
        if opt_ids and answer_key.option_id not in opt_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="answer_key.option_id must match an option id")

    if question_type == QuestionDocType.multi_choice:
        if not options:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="options are required for multi_choice")
        if answer_key.type != AnswerKeyType.multi:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="multi_choice requires answer_key.type=multi")
        if not answer_key.option_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="answer_key.option_ids is required")
        missing = [oid for oid in answer_key.option_ids if oid not in opt_ids]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"answer_key.option_ids missing in options: {missing}"
            )

    if question_type in (QuestionDocType.integer, QuestionDocType.short_text):
        if answer_key.type != AnswerKeyType.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="value questions require answer_key.type=value")
        if not answer_key.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="answer_key.value is required")
        if options:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="options must be empty for value questions")


def _validate_taxonomy_for_published(taxonomy: Dict, usage_status: UsageStatus) -> None:
    if usage_status == UsageStatus.published and not taxonomy.get("subject_id"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="subject_id is required for published questions")


def _normalize_options(options: List[dict]) -> List[dict]:
    seen = set()
    normalized: List[dict] = []
    for opt in options:
        if opt["id"] in seen:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="option ids must be unique")
        seen.add(opt["id"])
        normalized.append({"id": opt["id"], "text": opt["text"]})
    return normalized


def _merge_nested(existing: dict, patch: dict) -> dict:
    merged = dict(existing)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged.get(key, {}), **value}
        else:
            merged[key] = value
    return merged


def create_question(data: QuestionDocCreate, repo: Optional[QuestionRepo] = None) -> QuestionFullView:
    repo = repo or get_question_repo()
    now = datetime.utcnow()
    question_id = f"q_{uuid.uuid4()}"

    payload = data.model_dump(mode="json")
    payload["options"] = _normalize_options(payload.get("options", []))
    _validate_answer_key(data.type, data.answer_key, payload["options"])
    _validate_taxonomy_for_published(payload["taxonomy"], data.usage.status)

    payload.update(
        {
            "_id": question_id,
            "question_id": question_id,
            "version": 1,
            "search_blob": _build_search_blob(payload),
            "created_at": now,
            "updated_at": now,
            "rand_key": random.random(),
            "schema_version": SCHEMA_VERSION,
        }
    )
    repo.insert(payload)
    return QuestionFullView(**payload)


def update_question(question_id: str, patch: QuestionDocUpdate, repo: Optional[QuestionRepo] = None) -> QuestionFullView:
    repo = repo or get_question_repo()
    existing = repo.find_by_id(question_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    update_data = patch.model_dump(exclude_unset=True, exclude_none=True, mode="json")
    merged = _merge_nested(existing, update_data)
    merged["options"] = _normalize_options(merged.get("options", []))

    qtype = merged.get("type") or existing.get("type")
    answer_key_raw = merged.get("answer_key") or existing.get("answer_key")
    answer_key = AnswerKey(**answer_key_raw)
    _validate_answer_key(QuestionDocType(qtype), answer_key, merged.get("options", []))
    usage_status = UsageStatus(merged.get("usage", {}).get("status", existing.get("usage", {}).get("status", "draft")))
    _validate_taxonomy_for_published(merged.get("taxonomy", {}), usage_status)

    should_recompute_search = any(field in update_data for field in ["text", "options", "tags", "taxonomy"])
    merged["updated_at"] = datetime.utcnow()
    merged["version"] = existing.get("version", 1) + 1
    if should_recompute_search:
        merged["search_blob"] = _build_search_blob(merged)
    patch_data = {k: v for k, v in merged.items() if k != "_id"}
    repo.update(question_id, patch_data)
    return QuestionFullView(**merged)


def get_question(
    question_id: str,
    include_solution: bool = False,
    include_answer_key: bool = False,
    repo: Optional[QuestionRepo] = None,
) -> QuestionDocResponse:
    repo = repo or get_question_repo()
    projection = dict(FULL_PROJECTION)
    if include_solution:
        projection.pop("solution", None)
    else:
        projection["solution"] = 0
    if include_answer_key:
        projection.pop("answer_key", None)
    else:
        projection["answer_key"] = 0
    doc = repo.find_by_id(question_id, projection=projection)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    if include_solution:
        return QuestionFullView(**doc)
    if include_answer_key:
        return QuestionPreviewView(**doc)
    return QuestionPublicView(**doc)


def _build_filters(
    subject_id: Optional[str],
    topic_ids: Optional[List[str]],
    target_exam_ids: Optional[List[str]],
    difficulty_min: Optional[int],
    difficulty_max: Optional[int],
    tags: Optional[List[str]],
    status_value: Optional[str],
    is_active: Optional[bool],
    include_legacy: bool = True,
) -> Dict[str, object]:
    if include_legacy:
        filters: Dict[str, object] = {"$or": [{"schema_version": SCHEMA_VERSION}, {"schema_version": {"$exists": False}}]}
    else:
        filters = {"schema_version": SCHEMA_VERSION}
    if subject_id:
        filters["taxonomy.subject_id"] = subject_id
    if topic_ids:
        filters["taxonomy.topic_ids"] = {"$in": topic_ids}
    if target_exam_ids:
        filters["taxonomy.target_exam_ids"] = {"$in": target_exam_ids}
    if difficulty_min is not None or difficulty_max is not None:
        bounds: Dict[str, int] = {}
        if difficulty_min is not None:
            bounds["$gte"] = difficulty_min
        if difficulty_max is not None:
            bounds["$lte"] = difficulty_max
        filters["difficulty"] = bounds
    if tags:
        filters["tags"] = {"$in": tags}
    if status_value:
        filters["usage.status"] = status_value
    if is_active is not None:
        filters["usage.is_active"] = is_active
    return filters


def discover_questions(
    subject_id: Optional[str] = None,
    topic_ids: Optional[List[str]] = None,
    target_exam_ids: Optional[List[str]] = None,
    difficulty_min: Optional[int] = None,
    difficulty_max: Optional[int] = None,
    tags: Optional[List[str]] = None,
    status_value: Optional[str] = "published",
    is_active: Optional[bool] = True,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    repo: Optional[QuestionRepo] = None,
) -> PaginatedQuestions:
    repo = repo or get_question_repo()
    allowed_sorts = {"created_at", "difficulty", "updated_at"}
    if sort_by not in allowed_sorts:
        sort_by = "created_at"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"
    skip = max(0, skip)
    limit = max(0, min(limit, 200))
    filters = _build_filters(
        subject_id=subject_id,
        topic_ids=topic_ids,
        target_exam_ids=target_exam_ids,
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        tags=tags,
        status_value=status_value,
        is_active=is_active,
        include_legacy=True,
    )

    projection = dict(PUBLIC_PROJECTION)
    sort: List[Tuple[str, int]] = []

    if search:
        docs = repo.find_many(
            filters,
            projection=projection,
            sort=[("created_at", -1), ("_id", 1)],
            skip=skip,
            limit=limit,
            search=search,
            include_score=True,
        )
        total = repo.count(filters, search=search)
    else:
        direction = -1 if sort_order == "desc" else 1
        sort.append((sort_by, direction))
        sort.append(("_id", 1))
        docs = repo.find_many(filters, projection=projection, sort=sort, skip=skip, limit=limit)
        total = repo.count(filters)
    items: List[QuestionPublicView] = []
    for doc in docs:
        try:
            items.append(QuestionPublicView(**doc))
        except Exception:
            # Skip documents that do not match the v2 schema (e.g., legacy records)
            continue
    total = total if total else len(items)
    return PaginatedQuestions(items=items, total=total, skip=skip, limit=limit)


def sample_questions(
    subject_id: Optional[str] = None,
    topic_ids: Optional[List[str]] = None,
    target_exam_ids: Optional[List[str]] = None,
    difficulty_min: Optional[int] = None,
    difficulty_max: Optional[int] = None,
    tags: Optional[List[str]] = None,
    status_value: Optional[str] = "published",
    is_active: Optional[bool] = True,
    limit: int = 1,
    seed: Optional[str] = None,
    repo: Optional[QuestionRepo] = None,
) -> List[QuestionPublicView]:
    repo = repo or get_question_repo()
    limit = max(1, min(limit, 50))
    filters = _build_filters(
        subject_id=subject_id,
        topic_ids=topic_ids,
        target_exam_ids=target_exam_ids,
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        tags=tags,
        status_value=status_value,
        is_active=is_active,
        include_legacy=True,
    )
    projection = dict(PUBLIC_PROJECTION)
    docs = repo.sample(filters=filters, limit=limit, seed=seed)
    # apply projection for sample (since repo.sample may not project)
    projected: List[Dict] = []
    for doc in docs:
        projected_doc = {k: v for k, v in doc.items() if k not in projection}
        projected.append(projected_doc)
    items: List[QuestionPublicView] = []
    for doc in projected:
        try:
            items.append(QuestionPublicView(**doc))
        except Exception:
            continue
    return items
