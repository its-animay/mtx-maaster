import pytest
from fastapi import HTTPException

from app.db.questions_repo import InMemoryQuestionRepo
from app.schemas.question_doc import (
    AnswerKey,
    AnswerKeyType,
    QuestionDocCreate,
    QuestionDocType,
    TaxonomyDoc,
    UsageDoc,
    UsageStatus,
    OptionDoc,
)
from app.services.question_service import (
    create_question,
    discover_questions,
    get_question,
    sample_questions,
)


def _base_payload(**overrides):
    payload = QuestionDocCreate(
        text="What is 2+2?",
        type=QuestionDocType.single_choice,
        options=[OptionDoc(id="A", text="4"), OptionDoc(id="B", text="5")],
        answer_key=AnswerKey(type=AnswerKeyType.single, option_id="A"),
        taxonomy=TaxonomyDoc(subject_id="math", topic_ids=["algebra"], target_exam_ids=["exam_math"]),
        difficulty=2,
        tags=["arith", "easy"],
        usage=UsageDoc(status=UsageStatus.published, is_active=True),
    )
    for key, value in overrides.items():
        setattr(payload, key, value)
    return payload


def test_create_validation_requires_options_for_single_choice():
    repo = InMemoryQuestionRepo()
    payload = _base_payload(options=[])
    with pytest.raises(HTTPException):
        create_question(payload, repo=repo)


def test_discover_filters_by_subject_and_difficulty():
    repo = InMemoryQuestionRepo()
    create_question(_base_payload(), repo=repo)
    create_question(
        _base_payload(
            text="Hard one",
            difficulty=4,
            taxonomy=TaxonomyDoc(subject_id="physics", topic_ids=["mechanics"], target_exam_ids=[]),
        ),
        repo=repo,
    )

    result = discover_questions(subject_id="math", difficulty_max=3, repo=repo)
    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].taxonomy.subject_id == "math"


def test_sample_deterministic_with_seed():
    repo = InMemoryQuestionRepo()
    for idx in range(3):
        create_question(
            _base_payload(text=f"Q{idx}", tags=[f"t{idx}"], difficulty=idx + 1),
            repo=repo,
        )
    first = sample_questions(limit=2, seed="seed123", repo=repo)
    second = sample_questions(limit=2, seed="seed123", repo=repo)
    assert [q.text for q in first] == [q.text for q in second]


def test_get_question_projections():
    repo = InMemoryQuestionRepo()
    created = create_question(
        _base_payload(
            solution=None,
        ),
        repo=repo,
    )

    public_view = get_question(created.question_id, repo=repo)
    assert "answer_key" not in public_view.model_dump()

    preview_view = get_question(created.question_id, include_answer_key=True, repo=repo)
    assert preview_view.answer_key is not None

    full_view = get_question(created.question_id, include_solution=True, include_answer_key=True, repo=repo)
    assert full_view.answer_key is not None
