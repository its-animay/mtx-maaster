import uuid
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import HTTPException, status

from app.db.session import Database, get_db
from app.schemas.master import SubjectResponse
from app.schemas.question import QuestionResponse, QuestionType
from app.schemas.test import (
    AddQuestionsRequest,
    BulkAddRequest,
    QuestionReference,
    PaginatedTests,
    ReleaseMode,
    ReplaceQuestionRequest,
    ReorderRequest,
    TestCreate,
    TestResponse,
    TestStatus,
    TestUpdate,
    TestStats,
    UpdateMarksRequest,
    ValidationResult,
    TestSection,
)


def _get_test(test_id: str, db: Database) -> TestResponse:
    test = db.get_test(test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return test


def _get_section(test: TestResponse, section_id: str) -> TestSection:
    for section in test.pattern.sections:
        if section.section_id == section_id:
            return section
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")


def _ensure_series_exists(series_id: Optional[str], db: Database) -> None:
    """Validate series existence unless it's an auto-generated standalone id."""

    if series_id is None:
        return
    if str(series_id).startswith("standalone_"):
        return
    series = db.get_test_series(series_id)
    if not series:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test series not found")


def _validate_sections(pattern, db: Database) -> None:
    section_ids = set()
    for section in pattern.sections:
        if section.section_id in section_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate section_id in pattern")
        section_ids.add(section.section_id)
        subject: Optional[SubjectResponse] = db.get_subject(section.subject_id)
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subject {section.subject_id} not found for section {section.section_id}",
            )
    total_section_questions = sum(s.total_questions for s in pattern.sections)
    if pattern.total_questions != total_section_questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="pattern.total_questions must equal sum of section total_questions",
        )


def _ensure_test_uniques(code: str, slug: str, series_id: Optional[str], test_number: Optional[int], db: Database) -> None:
    if db.get_test_by_code(code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Test code already exists")
    if db.get_test_by_slug(slug):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Test slug already exists")
    if series_id and test_number is not None:
        if db.get_test_by_series_and_number(series_id, test_number):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="test_number already exists in series")


def _basic_question_set_checks(test: TestResponse) -> None:
    question_ids = [q.question_id for q in test.questions]
    if len(question_ids) != len(set(question_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate question_ids in test")
    if test.questions:
        _ensure_sequences_contiguous(test.questions)
    section_counts = Counter(q.section_id for q in test.questions)
    for section in test.pattern.sections:
        if section_counts.get(section.section_id, 0) > section.total_questions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Section {section.section_id} exceeds total_questions",
            )
    if len(test.questions) > test.pattern.total_questions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Test question limit exceeded")


def _build_question_ref(
    section: TestSection,
    question: QuestionResponse,
    seq: int,
    marks_override: Optional[float],
    negative_override: Optional[float],
    is_bonus: bool,
    is_optional: bool,
) -> QuestionReference:
    if section.subject_id != question.subject_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Question {question.question_id} does not belong to section subject {section.subject_id}",
        )
    scheme = section.marking_scheme.get(question.question_type)
    if not scheme:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No marking scheme for {question.question_type} in section {section.section_id}",
        )
    marks = marks_override if marks_override is not None else scheme.correct
    negative = negative_override if negative_override is not None else scheme.incorrect
    return QuestionReference(
        seq=seq,
        section_id=section.section_id,
        question_id=question.question_id,
        question_type=question.question_type,
        subject_id=question.subject_id,
        topic_ids=question.topic_ids,
        difficulty=question.difficulty,
        marks=marks,
        negative_marks=negative,
        is_bonus=is_bonus,
        is_optional=is_optional,
    )


def _ensure_sequences_contiguous(questions: List[QuestionReference]) -> None:
    if not questions:
        return
    seqs = sorted(q.seq for q in questions)
    expected = list(range(1, len(seqs) + 1))
    if seqs != expected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question sequences must be continuous starting from 1 without gaps",
        )


def create_test(data: TestCreate, db: Optional[Database] = None) -> TestResponse:
    db = db or get_db()
    # Allow standalone tests without an explicit series by generating a unique series_id
    if data.series_id:
        series_id = data.series_id
        test_number = data.test_number if data.test_number is not None else 0
    else:
        series_id = f"standalone_{uuid.uuid4()}"
        test_number = data.test_number if data.test_number is not None else 1
    _ensure_series_exists(series_id, db)
    _ensure_test_uniques(data.code, data.slug, series_id, test_number, db)
    _validate_sections(data.pattern, db)

    now = datetime.utcnow()
    base_fields = data.model_dump(exclude={"questions", "series_id", "test_number"})
    test = TestResponse(
        test_id=f"test_{uuid.uuid4()}",
        created_at=now,
        updated_at=now,
        questions=data.questions,
        series_id=series_id,
        test_number=test_number,
        **base_fields,
    )
    _basic_question_set_checks(test)
    db.insert_test(test)
    return test


def get_test(test_id: str, db: Optional[Database] = None) -> TestResponse:
    db = db or get_db()
    return _get_test(test_id, db)


def list_tests(
    db: Optional[Database] = None,
    series_id: Optional[str] = None,
    status: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
    include_questions: bool = True,
    sort_by: str = "test_number",
    sort_order: str = "asc",
) -> PaginatedTests:
    db = db or get_db()
    items, total = db.list_tests(
        series_id=series_id,
        status=status,
        is_active=is_active,
        skip=skip,
        limit=limit,
        include_questions=include_questions,
        sort_by=sort_by,
        sort_order=sort_order,
        include_total=True,
    )
    return PaginatedTests(items=items, total=total, skip=skip, limit=limit)


def update_test(test_id: str, payload: TestUpdate, db: Optional[Database] = None) -> TestResponse:
    db = db or get_db()
    existing = _get_test(test_id, db)
    update_data = payload.model_dump(exclude_unset=True)
    if "series_id" in update_data or "test_number" in update_data or "test_id" in update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify identifiers (series_id, test_number, test_id)",
        )

    merged = existing.copy(update=update_data)
    if merged.pattern:
        _validate_sections(merged.pattern, db)
        section_ids = {s.section_id for s in merged.pattern.sections}
        for question in merged.questions:
            if question.section_id not in section_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Question {question.question_id} belongs to removed section {question.section_id}",
                )
    _basic_question_set_checks(merged)
    merged.updated_at = datetime.utcnow()
    db.update_test(merged)
    return merged


def delete_test(test_id: str, db: Optional[Database] = None) -> None:
    db = db or get_db()
    _get_test(test_id, db)
    db.delete_test(test_id)


def _fetch_questions_or_fail(question_ids: List[str], db: Database) -> List[QuestionResponse]:
    found = db.get_questions_by_ids(question_ids)
    found_ids = {q.question_id for q in found}
    missing = [qid for qid in question_ids if qid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Questions not found: {missing}",
        )
    return found


def _next_seq(questions: List[QuestionReference]) -> int:
    if not questions:
        return 1
    return max(q.seq for q in questions) + 1


def add_questions_to_test(test_id: str, payload: AddQuestionsRequest, db: Optional[Database] = None) -> List[QuestionReference]:
    db = db or get_db()
    test = _get_test(test_id, db)
    section = _get_section(test, payload.section_id)

    if not payload.question_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="question_ids required")
    if payload.starting_seq is not None and payload.starting_seq < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="starting_seq must be >= 1")

    existing_ids = {q.question_id for q in test.questions}
    duplicate = [qid for qid in payload.question_ids if qid in existing_ids]
    if duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Duplicate questions already in test: {duplicate}")

    questions = _fetch_questions_or_fail(payload.question_ids, db)
    start_seq = payload.starting_seq or _next_seq(test.questions)

    new_refs: List[QuestionReference] = []
    seq = start_seq
    for question in questions:
        new_refs.append(
            _build_question_ref(
                section=section,
                question=question,
                seq=seq,
                marks_override=payload.marks,
                negative_override=payload.negative_marks,
                is_bonus=payload.is_bonus,
                is_optional=payload.is_optional,
            )
        )
        seq += 1

    updated_questions = sorted(test.questions + new_refs, key=lambda q: q.seq)

    section_count = len([q for q in updated_questions if q.section_id == section.section_id])
    if section_count > section.total_questions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Section question limit exceeded")
    if len(updated_questions) > test.pattern.total_questions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Test question limit exceeded")

    _ensure_sequences_contiguous(updated_questions)

    test.questions = updated_questions
    test.updated_at = datetime.utcnow()
    db.update_test(test)
    return new_refs


def bulk_add_questions(test_id: str, payload: BulkAddRequest, db: Optional[Database] = None) -> List[QuestionReference]:
    db = db or get_db()
    test = _get_test(test_id, db)
    section = _get_section(test, payload.section_id)

    if payload.count <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="count must be greater than 0")

    if payload.criteria.subject_id != section.subject_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Criteria subject_id must match section subject_id",
        )

    query: dict = {"subject_id": payload.criteria.subject_id, "is_active": True}
    if payload.criteria.topic_ids:
        query["topic_ids"] = {"$in": payload.criteria.topic_ids}
    if payload.criteria.difficulty:
        query["difficulty"] = {"$in": payload.criteria.difficulty}
    if payload.criteria.question_types:
        query["question_type"] = {"$in": [q.value for q in payload.criteria.question_types]}

    strategy = payload.strategy or "random"
    if strategy == "random":
        questions = db.find_questions(query, sample=payload.count)
    elif strategy == "difficulty_sorted":
        questions = db.find_questions(query, limit=payload.count, sort=[("difficulty", 1)])
    else:
        questions = db.find_questions(query, limit=payload.count, sort=[("question_id", 1)])

    if len(questions) < payload.count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only found {len(questions)} questions matching criteria; requested {payload.count}",
        )

    existing_ids = {q.question_id for q in test.questions}
    duplicates = [q.question_id for q in questions if q.question_id in existing_ids]
    if duplicates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Questions already present in test: {duplicates}",
        )

    start_seq = payload.starting_seq or _next_seq(test.questions)
    new_refs: List[QuestionReference] = []
    seq = start_seq
    for question in questions[: payload.count]:
        new_refs.append(
            _build_question_ref(
                section=section,
                question=question,
                seq=seq,
                marks_override=None,
                negative_override=None,
                is_bonus=False,
                is_optional=False,
            )
        )
        seq += 1

    updated_questions = sorted(test.questions + new_refs, key=lambda q: q.seq)
    _ensure_sequences_contiguous(updated_questions)

    test.questions = updated_questions
    test.updated_at = datetime.utcnow()
    db.update_test(test)
    return new_refs


def remove_question(test_id: str, question_id: str, db: Optional[Database] = None) -> None:
    db = db or get_db()
    test = _get_test(test_id, db)
    if question_id not in {q.question_id for q in test.questions}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found in test")
    test.questions = [q for q in test.questions if q.question_id != question_id]
    # Resequence to keep contiguous order
    test.questions = sorted(test.questions, key=lambda q: q.seq)
    for idx, ref in enumerate(test.questions, start=1):
        ref.seq = idx
    _ensure_sequences_contiguous(test.questions)
    test.updated_at = datetime.utcnow()
    db.update_test(test)


def reorder_questions(test_id: str, payload: ReorderRequest, db: Optional[Database] = None) -> List[QuestionReference]:
    db = db or get_db()
    test = _get_test(test_id, db)
    section = _get_section(test, payload.section_id)
    updates = payload.question_sequence
    question_map = {q.question_id: q for q in test.questions}
    for item in updates:
        qid = item.get("question_id") or item.get("id")
        seq = item.get("seq")
        if not qid or seq is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each item requires question_id and seq")
        if int(seq) < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sequence numbers must be >= 1")
        ref = question_map.get(qid)
        if not ref:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Question {qid} not found in test")
        if ref.section_id != section.section_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question {qid} does not belong to section {section.section_id}",
            )
        ref.seq = int(seq)

    # Ensure no duplicate seq values
    seqs = [q.seq for q in test.questions]
    if len(seqs) != len(set(seqs)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate sequence numbers not allowed")
    _ensure_sequences_contiguous(test.questions)
    test.updated_at = datetime.utcnow()
    db.update_test(test)
    return sorted(test.questions, key=lambda q: q.seq)


def replace_question(
    test_id: str,
    old_question_id: str,
    payload: ReplaceQuestionRequest,
    db: Optional[Database] = None,
) -> QuestionReference:
    db = db or get_db()
    test = _get_test(test_id, db)
    ref = next((q for q in test.questions if q.question_id == old_question_id), None)
    if not ref:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found in test")
    section = _get_section(test, ref.section_id)

    if payload.new_question_id in {q.question_id for q in test.questions if q.question_id != old_question_id}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New question already present in test")

    new_question = _fetch_questions_or_fail([payload.new_question_id], db)[0]
    new_ref = _build_question_ref(
        section=section,
        question=new_question,
        seq=ref.seq if payload.preserve_sequence else _next_seq(test.questions),
        marks_override=ref.marks,
        negative_override=ref.negative_marks,
        is_bonus=ref.is_bonus,
        is_optional=ref.is_optional,
    )
    # Replace
    for idx, q in enumerate(test.questions):
        if q.question_id == old_question_id:
            test.questions[idx] = new_ref
            break
    test.questions = sorted(test.questions, key=lambda q: q.seq)
    _ensure_sequences_contiguous(test.questions)
    test.updated_at = datetime.utcnow()
    db.update_test(test)
    return new_ref


def update_question_marks(
    test_id: str, question_id: str, payload: UpdateMarksRequest, db: Optional[Database] = None
) -> QuestionReference:
    db = db or get_db()
    test = _get_test(test_id, db)
    ref = next((q for q in test.questions if q.question_id == question_id), None)
    if not ref:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found in test")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(ref, field, value)
    test.updated_at = datetime.utcnow()
    db.update_test(test)
    return ref


def _build_question_map(question_ids: List[str], db: Database) -> Dict[str, QuestionResponse]:
    questions = db.get_questions_by_ids(question_ids)
    return {q.question_id: q for q in questions}


def _ensure_solutions_released(test: TestResponse) -> None:
    cfg = test.solutions
    if not cfg.has_solutions or cfg.release_mode == ReleaseMode.never:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solutions are not available")
    if cfg.release_mode == ReleaseMode.scheduled:
        if not cfg.release_at:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solutions release not scheduled")
        if datetime.utcnow() < cfg.release_at:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solutions not released yet")
    if cfg.release_mode == ReleaseMode.manual:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solutions require manual release")


def get_test_preview(test_id: str, db: Optional[Database] = None) -> dict:
    db = db or get_db()
    test = _get_test(test_id, db)
    question_ids = [q.question_id for q in test.questions]
    q_map = _build_question_map(question_ids, db)
    missing = [qid for qid in question_ids if qid not in q_map]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Missing questions: {missing}")

    merged_questions = []
    for ref in sorted(test.questions, key=lambda q: q.seq):
        q = q_map[ref.question_id]
        q_data = q.model_dump()
        for ans_field in ("correct_option_id", "correct_option_ids", "answer_value", "solution"):
            q_data.pop(ans_field, None)
        merged_questions.append({**ref.model_dump(), **q_data})

    response = test.model_dump()
    response["questions"] = merged_questions
    return response


def get_test_with_solutions(test_id: str, db: Optional[Database] = None) -> dict:
    db = db or get_db()
    test = _get_test(test_id, db)
    _ensure_solutions_released(test)
    q_map = _build_question_map([q.question_id for q in test.questions], db)
    missing = [qid for qid in [q.question_id for q in test.questions] if qid not in q_map]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Missing questions: {missing}")
    merged_questions = []
    for ref in sorted(test.questions, key=lambda q: q.seq):
        q = q_map[ref.question_id]
        merged_questions.append({**ref.model_dump(), **q.model_dump()})
    response = test.model_dump()
    response["questions"] = merged_questions
    return response


def get_answer_key(test_id: str, db: Optional[Database] = None) -> Dict[str, object]:
    db = db or get_db()
    test = _get_test(test_id, db)
    _ensure_solutions_released(test)
    q_map = _build_question_map([q.question_id for q in test.questions], db)
    missing = [qid for qid in [q.question_id for q in test.questions] if qid not in q_map]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Missing questions: {missing}")
    answer_key: Dict[str, object] = {}
    for ref in test.questions:
        q = q_map[ref.question_id]
        if q.question_type == QuestionType.MCQ:
            answer_key[q.question_id] = q.correct_option_id
        elif q.question_type == QuestionType.MSQ:
            answer_key[q.question_id] = q.correct_option_ids or []
        elif q.question_type == QuestionType.NAT:
            answer_key[q.question_id] = q.answer_value
        else:
            answer_key[q.question_id] = None
    return answer_key


def validate_test(test_id: str, db: Optional[Database] = None) -> ValidationResult:
    db = db or get_db()
    test = _get_test(test_id, db)
    issues: List[str] = []
    warnings: List[str] = []

    total_questions = len(test.questions)
    if total_questions != test.pattern.total_questions:
        issues.append("Total questions do not match pattern.total_questions")

    section_counts = Counter(q.section_id for q in test.questions)
    for section in test.pattern.sections:
        if section_counts.get(section.section_id, 0) != section.total_questions:
            issues.append(f"Section {section.section_id} question count mismatch")

    seqs = [q.seq for q in test.questions]
    if len(seqs) != len(set(seqs)):
        issues.append("Duplicate sequence numbers found")
    try:
        _ensure_sequences_contiguous(test.questions)
    except HTTPException as exc:  # type: ignore
        issues.append(str(exc.detail))

    question_ids = [q.question_id for q in test.questions]
    found = db.get_questions_by_ids(question_ids)
    found_ids = {q.question_id for q in found}
    missing = [qid for qid in question_ids if qid not in found_ids]
    if missing:
        issues.append(f"Missing question documents: {missing}")
    q_map = {q.question_id: q for q in found}
    for ref in test.questions:
        q = q_map.get(ref.question_id)
        if q and q.subject_id != ref.subject_id:
            issues.append(f"Subject mismatch for question {ref.question_id}")

    return ValidationResult(is_valid=len(issues) == 0, issues=issues, warnings=warnings)


def test_stats(test_id: str, db: Optional[Database] = None) -> TestStats:
    db = db or get_db()
    test = _get_test(test_id, db)
    difficulty_counts: Dict[int, int] = dict(Counter(q.difficulty for q in test.questions))
    type_counts: Dict[QuestionType, int] = dict(Counter(q.question_type for q in test.questions))
    topic_counts: Dict[str, int] = defaultdict(int)
    for q in test.questions:
        for topic_id in q.topic_ids:
            topic_counts[topic_id] += 1
    section_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for q in test.questions:
        section_stats[q.section_id]["count"] += 1
        section_stats[q.section_id][f"{q.question_type}"] += 1

    return TestStats(
        difficulty_distribution=difficulty_counts,
        type_distribution=type_counts,
        topic_coverage=dict(topic_counts),
        section_stats={k: dict(v) for k, v in section_stats.items()},
    )
