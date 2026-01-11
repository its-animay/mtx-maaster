from datetime import datetime
from typing import Dict, List, Optional

from pymongo import ASCENDING, DESCENDING, MongoClient

from app.core.config import get_settings

from app.schemas.exam import ExamResponse, ExamSyllabusItem
from app.schemas.master import SubjectResponse, TopicResponse
from app.schemas.question import OptionSchema, QuestionResponse, QuestionType
from app.schemas.test import QuestionReference, TestResponse, TestSection, SectionMarkingScheme, TestPattern
from app.schemas.test_series import SyllabusCoverageItem, TestSeriesResponse, SeriesStats


def _dt(value: datetime) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))


class Database:
    """
    Mongo-backed repository layer.

    Swapping to another database should only require replacing this class while
    preserving method signatures used by services.
    """

    def __init__(self, uri: Optional[str] = None, db_name: Optional[str] = None) -> None:
        settings = get_settings()
        self.uri = uri or settings.mongo_uri
        self.db_name = db_name or settings.mongo_db_name
        self.client = MongoClient(self.uri)
        self.db = self.client[self.db_name]
        self._init_indexes()

    def _init_indexes(self) -> None:
        self.db.subjects.create_index([("slug", ASCENDING)], unique=True)
        self.db.topics.create_index([("subject_id", ASCENDING), ("slug", ASCENDING)], unique=True)
        self.db.exams.create_index([("code", ASCENDING)], unique=True)
        self.db.questions.create_index([("subject_id", ASCENDING)])
        self.db.questions.create_index([("difficulty", ASCENDING), ("is_active", ASCENDING)])
        # Question document (v2) indexes
        self.db.questions.create_index([("schema_version", ASCENDING)])
        self.db.questions.create_index([("taxonomy.subject_id", ASCENDING)])
        self.db.questions.create_index([("taxonomy.topic_ids", ASCENDING)])
        self.db.questions.create_index([("taxonomy.target_exam_ids", ASCENDING)])
        self.db.questions.create_index([("difficulty", ASCENDING)])
        self.db.questions.create_index([("tags", ASCENDING)])
        self.db.questions.create_index([("usage.is_active", ASCENDING)])
        self.db.questions.create_index([("usage.status", ASCENDING)])
        self.db.questions.create_index(
            [("usage.is_active", ASCENDING), ("usage.status", ASCENDING), ("taxonomy.subject_id", ASCENDING), ("difficulty", ASCENDING)]
        )
        self.db.questions.create_index(
            [("taxonomy.subject_id", ASCENDING), ("taxonomy.topic_ids", ASCENDING), ("difficulty", ASCENDING)]
        )
        self.db.questions.create_index([("search_blob", "text")], name="question_search_text")
        self.db.test_series.create_index([("series_id", ASCENDING)], unique=True)
        self.db.test_series.create_index([("code", ASCENDING)], unique=True)
        self.db.test_series.create_index([("slug", ASCENDING)], unique=True)
        self.db.test_series.create_index([("target_exam_id", ASCENDING), ("is_active", ASCENDING)])
        self.db.test_series.create_index([("status", ASCENDING), ("is_active", ASCENDING), ("display_order", ASCENDING)])
        self.db.test_series.create_index([("tags", ASCENDING)])
        self.db.test_series.create_index([("available_from", ASCENDING)])
        self.db.test_series.create_index([("available_until", ASCENDING)])
        self.db.tests.create_index([("test_id", ASCENDING)], unique=True)
        self.db.tests.create_index([("code", ASCENDING)], unique=True)
        self.db.tests.create_index([("slug", ASCENDING)], unique=True)
        self.db.tests.create_index([("series_id", ASCENDING), ("test_number", ASCENDING)], unique=True)
        self.db.tests.create_index([("series_id", ASCENDING), ("status", ASCENDING), ("is_active", ASCENDING)])
        self.db.tests.create_index([("questions.question_id", ASCENDING)])
        self.db.tests.create_index([("status", ASCENDING), ("availability.starts_at", ASCENDING)])

    # Subject methods
    def insert_subject(self, subject: SubjectResponse) -> None:
        self.db.subjects.insert_one(subject.model_dump())

    def update_subject(self, subject: SubjectResponse) -> None:
        self.db.subjects.update_one({"id": subject.id}, {"$set": subject.dict(exclude={"id", "created_at"})})

    def delete_subject(self, subject_id: str) -> None:
        self.db.subjects.delete_one({"id": subject_id})

    def get_subject(self, subject_id: str) -> Optional[SubjectResponse]:
        doc = self.db.subjects.find_one({"id": subject_id})
        return self._subject_from_doc(doc) if doc else None

    def get_subject_by_slug(self, slug: str) -> Optional[SubjectResponse]:
        doc = self.db.subjects.find_one({"slug": slug})
        return self._subject_from_doc(doc) if doc else None

    def list_subjects(
        self,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 50,
        sort_by: str = "name",
        sort_order: str = "asc",
        include_total: bool = False,
    ) -> tuple[List[SubjectResponse], int]:
        query: dict = {}
        if is_active is not None:
            query["is_active"] = is_active
        if search:
            query["name"] = {"$regex": search, "$options": "i"}
        if tags:
            query["tags"] = {"$all": tags}

        sort_fields = {"name": "name", "created_at": "created_at", "updated_at": "updated_at", "slug": "slug"}
        sort_field = sort_fields.get(sort_by, "name")
        sort_dir = ASCENDING if sort_order.lower() != "desc" else DESCENDING

        total = self.db.subjects.count_documents(query) if include_total else 0
        cursor = (
            self.db.subjects.find(query)
            .skip(max(0, skip))
            .limit(limit)
            .sort([(sort_field, sort_dir)])
        )
        return [self._subject_from_doc(doc) for doc in cursor], total

    def _subject_from_doc(self, doc: dict) -> SubjectResponse:
        return SubjectResponse(
            id=doc["id"],
            name=doc["name"],
            slug=doc["slug"],
            description=doc.get("description"),
            tags=doc.get("tags", []),
            metadata=doc.get("metadata"),
            is_active=bool(doc.get("is_active", True)),
            created_at=_dt(doc["created_at"]),
            updated_at=_dt(doc["updated_at"]),
        )

    # Topic methods
    def insert_topic(self, topic: TopicResponse) -> None:
        self.db.topics.insert_one(topic.model_dump())

    def update_topic(self, topic: TopicResponse) -> None:
        self.db.topics.update_one({"id": topic.id}, {"$set": topic.dict(exclude={"id", "created_at"})})

    def delete_topic(self, topic_id: str) -> None:
        self.db.topics.delete_one({"id": topic_id})

    def get_topic(self, topic_id: str) -> Optional[TopicResponse]:
        doc = self.db.topics.find_one({"id": topic_id})
        return self._topic_from_doc(doc) if doc else None

    def get_topic_by_slug(self, subject_id: str, slug: str) -> Optional[TopicResponse]:
        doc = self.db.topics.find_one({"subject_id": subject_id, "slug": slug})
        return self._topic_from_doc(doc) if doc else None

    def list_topics(self, subject_id: Optional[str] = None) -> List[TopicResponse]:
        query = {"subject_id": subject_id} if subject_id else {}
        return [self._topic_from_doc(doc) for doc in self.db.topics.find(query)]

    def _topic_from_doc(self, doc: dict) -> TopicResponse:
        return TopicResponse(
            id=doc["id"],
            subject_id=doc["subject_id"],
            name=doc["name"],
            slug=doc["slug"],
            description=doc.get("description"),
            difficulty_weight=float(doc["difficulty_weight"]),
            bloom_level=doc.get("bloom_level"),
            related_topic_ids=doc.get("related_topic_ids", []),
            prerequisite_topic_ids=doc.get("prerequisite_topic_ids", []),
            tags=doc.get("tags", []),
            metadata=doc.get("metadata"),
            is_active=bool(doc.get("is_active", True)),
            created_at=_dt(doc["created_at"]),
            updated_at=_dt(doc["updated_at"]),
        )

    # Exam methods
    def insert_exam(self, exam: ExamResponse) -> None:
        payload = exam.model_dump()
        payload["syllabus"] = [item.model_dump() for item in exam.syllabus]
        self.db.exams.insert_one(payload)

    def update_exam(self, exam: ExamResponse) -> None:
        payload = exam.model_dump(exclude={"exam_id", "created_at"})
        payload["syllabus"] = [item.model_dump() for item in exam.syllabus]
        self.db.exams.update_one({"exam_id": exam.exam_id}, {"$set": payload})

    def delete_exam(self, exam_id: str) -> None:
        self.db.exams.delete_one({"exam_id": exam_id})

    def get_exam(self, exam_id: str) -> Optional[ExamResponse]:
        doc = self.db.exams.find_one({"exam_id": exam_id})
        return self._exam_from_doc(doc) if doc else None

    def get_exam_by_code(self, code: str) -> Optional[ExamResponse]:
        doc = self.db.exams.find_one({"code": code})
        return self._exam_from_doc(doc) if doc else None

    def list_exams(self, active_only: bool = False) -> List[ExamResponse]:
        query = {"is_active": True} if active_only else {}
        return [self._exam_from_doc(doc) for doc in self.db.exams.find(query)]

    def _exam_from_doc(self, doc: dict) -> ExamResponse:
        syllabus = [ExamSyllabusItem(**item) for item in doc.get("syllabus", [])]
        return ExamResponse(
            exam_id=doc["exam_id"],
            code=doc["code"],
            name=doc["name"],
            description=doc.get("description"),
            syllabus=syllabus,
            version=doc.get("version"),
            is_active=bool(doc.get("is_active", True)),
            metadata=doc.get("metadata"),
            created_by=doc.get("created_by"),
            created_at=_dt(doc["created_at"]),
            updated_at=_dt(doc["updated_at"]),
        )

    # Question methods
    def insert_question(self, question: QuestionResponse) -> None:
        payload = question.model_dump()
        payload["options"] = [opt.model_dump() for opt in question.options]
        self.db.questions.insert_one(payload)

    def update_question(self, question: QuestionResponse) -> None:
        payload = question.model_dump(exclude={"question_id", "created_at"})
        payload["options"] = [opt.model_dump() for opt in question.options]
        self.db.questions.update_one({"question_id": question.question_id}, {"$set": payload})

    def delete_question(self, question_id: str) -> None:
        self.db.questions.delete_one({"question_id": question_id})

    def get_question(self, question_id: str) -> Optional[QuestionResponse]:
        doc = self.db.questions.find_one({"question_id": question_id})
        return self._question_from_doc(doc) if doc else None

    def list_questions(self) -> List[QuestionResponse]:
        return [self._question_from_doc(doc) for doc in self.db.questions.find({})]

    def get_questions_by_ids(self, question_ids: List[str]) -> List[QuestionResponse]:
        if not question_ids:
            return []
        return [self._question_from_doc(doc) for doc in self.db.questions.find({"question_id": {"$in": question_ids}})]

    def find_questions(
        self,
        query: dict,
        limit: Optional[int] = None,
        sort: Optional[list] = None,
        sample: Optional[int] = None,
    ) -> List[QuestionResponse]:
        query = {**query, "schema_version": {"$ne": 2}}
        if sample:
            total = self.db.questions.count_documents(query)
            sample_size = min(sample, total) if total else 0
            if sample_size == 0:
                return []
            pipeline = [{"$match": query}, {"$sample": {"size": sample_size}}]
            cursor = self.db.questions.aggregate(pipeline)
            return [self._question_from_doc(doc) for doc in cursor]

        cursor = self.db.questions.find(query)
        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)
        return [self._question_from_doc(doc) for doc in cursor]

    def _question_from_doc(self, doc: dict) -> QuestionResponse:
        """
        Convert persisted question document to legacy QuestionResponse.

        Supports legacy schema and schema_version=2 from Questions Master by mapping
        answer_key/options into the legacy fields.
        """

        if doc.get("schema_version") == 2:
            qtype_raw = doc.get("type")
            type_map = {
                "single_choice": QuestionType.MCQ,
                "multi_choice": QuestionType.MSQ,
                "integer": QuestionType.NAT,
                "short_text": QuestionType.NAT,
                "true_false": QuestionType.MCQ,
            }
            qtype = type_map.get(qtype_raw, QuestionType.MCQ)

            options = [OptionSchema(id=opt["id"], content=opt.get("text", ""), rationale=None) for opt in doc.get("options", [])]
            answer_key = doc.get("answer_key", {}) or {}
            correct_option_id = answer_key.get("option_id")
            correct_option_ids = answer_key.get("option_ids")
            answer_value = answer_key.get("value")

            solution_obj = doc.get("solution") or {}
            solution_text = solution_obj.get("explanation")

            taxonomy = doc.get("taxonomy") or {}
            subject_id = taxonomy.get("subject_id")
            topic_ids = taxonomy.get("topic_ids", [])
            target_exam_tags = taxonomy.get("target_exam_ids", [])

            return QuestionResponse(
                question_id=doc["question_id"],
                question_type=qtype,
                subject_id=subject_id,
                topic_ids=topic_ids,
                text=doc.get("text", ""),
                options=options,
                correct_option_id=correct_option_id,
                correct_option_ids=correct_option_ids,
                answer_value=answer_value,
                difficulty=int(doc.get("difficulty", 1)),
                target_exam_tags=target_exam_tags,
                tags=doc.get("tags", []),
                source=doc.get("meta", {}).get("source") if doc.get("meta") else doc.get("source"),
                version=str(doc.get("version")) if doc.get("version") is not None else None,
                metadata=doc.get("meta") or doc.get("metadata"),
                solution=solution_text,
                is_active=bool(doc.get("usage", {}).get("is_active", True)),
                created_at=_dt(doc["created_at"]),
                updated_at=_dt(doc["updated_at"]),
            )

        return QuestionResponse(
            question_id=doc["question_id"],
            question_type=doc.get("question_type"),
            subject_id=doc["subject_id"],
            topic_ids=doc.get("topic_ids", []),
            text=doc["text"],
            options=[OptionSchema(**opt) for opt in doc.get("options", [])],
            correct_option_id=doc["correct_option_id"],
            correct_option_ids=doc.get("correct_option_ids"),
            answer_value=doc.get("answer_value"),
            difficulty=int(doc["difficulty"]),
            target_exam_tags=doc.get("target_exam_tags", []),
            tags=doc.get("tags", []),
            source=doc.get("source"),
            version=doc.get("version"),
            metadata=doc.get("metadata"),
            solution=doc.get("solution"),
            is_active=bool(doc.get("is_active", True)),
            created_at=_dt(doc["created_at"]),
            updated_at=_dt(doc["updated_at"]),
        )

    # Test series methods
    def insert_test_series(self, series: TestSeriesResponse) -> None:
        payload = series.model_dump()
        if series.syllabus_coverage:
            payload["syllabus_coverage"] = [item.model_dump() for item in series.syllabus_coverage]
        if series.stats:
            payload["stats"] = series.stats.model_dump()
        self.db.test_series.insert_one(payload)

    def update_test_series(self, series: TestSeriesResponse) -> None:
        payload = series.model_dump(exclude={"series_id", "created_at"})
        if series.syllabus_coverage:
            payload["syllabus_coverage"] = [item.model_dump() for item in series.syllabus_coverage]
        if series.stats:
            payload["stats"] = series.stats.model_dump()
        self.db.test_series.update_one({"series_id": series.series_id}, {"$set": payload})

    def delete_test_series(self, series_id: str) -> None:
        self.db.test_series.delete_one({"series_id": series_id})

    def get_test_series(self, series_id: str) -> Optional[TestSeriesResponse]:
        doc = self.db.test_series.find_one({"series_id": series_id})
        return self._series_from_doc(doc) if doc else None

    def get_test_series_by_code(self, code: str) -> Optional[TestSeriesResponse]:
        doc = self.db.test_series.find_one({"code": code})
        return self._series_from_doc(doc) if doc else None

    def get_test_series_by_slug(self, slug: str) -> Optional[TestSeriesResponse]:
        doc = self.db.test_series.find_one({"slug": slug})
        return self._series_from_doc(doc) if doc else None

    def list_test_series(
        self,
        target_exam_id: Optional[str] = None,
        series_type: Optional[str] = None,
        status: Optional[str] = None,
        is_active: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 50,
        sort_by: str = "display_order",
        sort_order: str = "asc",
        include_total: bool = False,
    ) -> tuple[List[TestSeriesResponse], int]:
        query: dict = {}
        if target_exam_id:
            query["target_exam_id"] = target_exam_id
        if series_type:
            query["series_type"] = series_type
        if status:
            query["status"] = status
        if is_active is not None:
            query["is_active"] = is_active
        if tags:
            query["tags"] = {"$all": tags}

        sort_fields = {
            "display_order": "display_order",
            "created_at": "created_at",
            "updated_at": "updated_at",
            "name": "name",
        }
        sort_field = sort_fields.get(sort_by, "display_order")
        sort_dir = ASCENDING if sort_order.lower() != "desc" else DESCENDING

        total = self.db.test_series.count_documents(query) if include_total else 0
        cursor = (
            self.db.test_series.find(query)
            .skip(max(0, skip))
            .limit(limit)
            .sort([(sort_field, sort_dir)])
        )
        return [self._series_from_doc(doc) for doc in cursor], total

    def _series_from_doc(self, doc: dict) -> TestSeriesResponse:
        syllabus_coverage = [SyllabusCoverageItem(**item) for item in doc.get("syllabus_coverage", [])]
        stats = SeriesStats(**doc["stats"]) if doc.get("stats") else None
        return TestSeriesResponse(
            series_id=doc["series_id"],
            code=doc["code"],
            slug=doc["slug"],
            name=doc["name"],
            description=doc.get("description"),
            target_exam_id=doc["target_exam_id"],
            series_type=doc.get("series_type"),
            difficulty_level=doc.get("difficulty_level"),
            total_tests=doc.get("total_tests"),
            syllabus_coverage=syllabus_coverage,
            status=doc.get("status", "draft"),
            is_active=bool(doc.get("is_active", True)),
            available_from=_dt(doc["available_from"]) if doc.get("available_from") else None,
            available_until=_dt(doc["available_until"]) if doc.get("available_until") else None,
            tags=doc.get("tags", []),
            language=doc.get("language"),
            version=doc.get("version"),
            display_order=int(doc.get("display_order", 0)),
            stats=stats,
            metadata=doc.get("metadata"),
            created_at=_dt(doc["created_at"]),
            updated_at=_dt(doc["updated_at"]),
        )

    # Test methods
    def insert_test(self, test: TestResponse) -> None:
        payload = test.model_dump()
        payload["questions"] = [q.model_dump() for q in test.questions]
        payload["pattern"]["sections"] = [
            {
                **section.model_dump(),
                "marking_scheme": {k.value if hasattr(k, "value") else str(k): v.model_dump() for k, v in section.marking_scheme.items()},
            }
            for section in test.pattern.sections
        ]
        self.db.tests.insert_one(payload)

    def update_test(self, test: TestResponse) -> None:
        payload = test.model_dump(exclude={"test_id", "created_at"})
        payload["questions"] = [q.model_dump() for q in test.questions]
        payload["pattern"]["sections"] = [
            {
                **section.model_dump(),
                "marking_scheme": {k.value if hasattr(k, "value") else str(k): v.model_dump() for k, v in section.marking_scheme.items()},
            }
            for section in test.pattern.sections
        ]
        self.db.tests.update_one({"test_id": test.test_id}, {"$set": payload})

    def delete_test(self, test_id: str) -> None:
        self.db.tests.delete_one({"test_id": test_id})

    def get_test(self, test_id: str) -> Optional[TestResponse]:
        doc = self.db.tests.find_one({"test_id": test_id})
        return self._test_from_doc(doc) if doc else None

    def get_test_by_code(self, code: str) -> Optional[TestResponse]:
        doc = self.db.tests.find_one({"code": code})
        return self._test_from_doc(doc) if doc else None

    def get_test_by_slug(self, slug: str) -> Optional[TestResponse]:
        doc = self.db.tests.find_one({"slug": slug})
        return self._test_from_doc(doc) if doc else None

    def list_tests(
        self,
        series_id: Optional[str] = None,
        status: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
        include_questions: bool = True,
        sort_by: str = "test_number",
        sort_order: str = "asc",
        include_total: bool = False,
    ) -> tuple[List[TestResponse], int]:
        query: dict = {}
        if series_id:
            query["series_id"] = series_id
        if status:
            query["status"] = status
        if is_active is not None:
            query["is_active"] = is_active
        projection = None if include_questions else {"questions": 0}
        sort_fields = {
            "test_number": "test_number",
            "created_at": "created_at",
            "updated_at": "updated_at",
            "name": "name",
        }
        sort_field = sort_fields.get(sort_by, "test_number")
        sort_dir = ASCENDING if sort_order.lower() != "desc" else DESCENDING
        total = self.db.tests.count_documents(query) if include_total else 0
        cursor = (
            self.db.tests.find(query, projection)
            .skip(max(0, skip))
            .limit(limit)
            .sort([(sort_field, sort_dir)])
        )
        return [self._test_from_doc(doc, include_questions=include_questions) for doc in cursor], total

    def get_test_by_series_and_number(self, series_id: str, test_number: int) -> Optional[TestResponse]:
        doc = self.db.tests.find_one({"series_id": series_id, "test_number": test_number})
        return self._test_from_doc(doc) if doc else None

    def count_tests_for_series(self, series_id: str) -> int:
        return self.db.tests.count_documents({"series_id": series_id})

    def aggregate_series_stats(self, series_id: str) -> dict:
        pipeline = [
            {"$match": {"series_id": series_id}},
            {
                "$group": {
                    "_id": "$series_id",
                    "total_tests": {"$sum": 1},
                    "total_questions": {"$sum": {"$size": {"$ifNull": ["$questions", []]}}},
                    "total_duration_minutes": {"$sum": "$pattern.total_duration_minutes"},
                    "avg_difficulty": {"$avg": {"$avg": "$questions.difficulty"}},
                }
            },
        ]
        result = list(self.db.tests.aggregate(pipeline))
        return result[0] if result else {}

    def _test_from_doc(self, doc: dict, include_questions: bool = True) -> TestResponse:
        sections: List[TestSection] = []
        for section in doc["pattern"].get("sections", []):
            marking_raw = section.get("marking_scheme", {}) or {}
            marking: Dict[QuestionType, SectionMarkingScheme] = {}
            for key, value in marking_raw.items():
                qtype = QuestionType(key)
                marking[qtype] = SectionMarkingScheme(**value) if isinstance(value, dict) else value
            sections.append(
                TestSection(
                    section_id=section["section_id"],
                    section_code=section["section_code"],
                    name=section["name"],
                    display_order=int(section.get("display_order", 0)),
                    subject_id=section["subject_id"],
                    total_questions=int(section["total_questions"]),
                    total_marks=section.get("total_marks"),
                    duration_minutes=section.get("duration_minutes"),
                    can_switch_section=bool(section.get("can_switch_section", True)),
                    is_optional=bool(section.get("is_optional", False)),
                    marking_scheme=marking,
                )
            )

        pattern = TestPattern(
            total_duration_minutes=doc["pattern"].get("total_duration_minutes"),
            total_marks=doc["pattern"].get("total_marks"),
            total_questions=doc["pattern"].get("total_questions"),
            sections=sections,
        )
        questions = []
        if include_questions:
            for q in doc.get("questions", []):
                questions.append(
                    QuestionReference(
                        seq=int(q["seq"]),
                        section_id=q["section_id"],
                        question_id=q["question_id"],
                        question_type=QuestionType(q["question_type"]),
                        subject_id=q["subject_id"],
                        topic_ids=q.get("topic_ids", []),
                        difficulty=int(q["difficulty"]),
                        marks=q.get("marks"),
                        negative_marks=q.get("negative_marks"),
                        is_bonus=bool(q.get("is_bonus", False)),
                        is_optional=bool(q.get("is_optional", False)),
                    )
                )

        return TestResponse(
            test_id=doc["test_id"],
            code=doc["code"],
            slug=doc["slug"],
            series_id=doc.get("series_id"),
            test_number=int(doc["test_number"]) if doc.get("test_number") is not None else None,
            name=doc["name"],
            description=doc.get("description"),
            pattern=pattern,
            settings=doc.get("settings", {}),
            solutions=doc.get("solutions", {}),
            availability=doc.get("availability", {}),
            is_active=bool(doc.get("is_active", True)),
            status=doc.get("status", "draft"),
            tags=doc.get("tags", []),
            version=doc.get("version"),
            language=doc.get("language"),
            metadata=doc.get("metadata"),
            questions=questions,
            created_at=_dt(doc["created_at"]),
            updated_at=_dt(doc["updated_at"]),
        )

    # Maintenance helpers
    def clear_all(self) -> None:
        self.db.questions.delete_many({})
        self.db.exams.delete_many({})
        self.db.topics.delete_many({})
        self.db.subjects.delete_many({})


db_instance = Database()


def get_db() -> Database:
    """Return the singleton database repository."""

    return db_instance


def init_db() -> None:
    """Seed the database with initial masters, exam, and questions."""

    db = get_db()
    # Safety: do not wipe existing data; seed only if empty.
    subjects, _ = db.list_subjects()
    if subjects:
        return

    now = datetime.utcnow()

    physics = SubjectResponse(
        id="subject_physics",
        name="Physics",
        slug="physics",
        description="Physics master subject",
        tags=["science"],
        metadata={"owner": "curriculum-team"},
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.insert_subject(physics)

    thermodynamics = TopicResponse(
        id="topic_thermodynamics",
        subject_id=physics.id,
        name="Thermodynamics",
        slug="thermodynamics",
        description="Thermodynamics fundamentals",
        difficulty_weight=0.7,
        bloom_level="Analyze",
        related_topic_ids=[],
        prerequisite_topic_ids=[],
        tags=["heat", "energy"],
        metadata={"chapter": "First Law"},
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.insert_topic(thermodynamics)

    syllabus_item = ExamSyllabusItem(subject_id=physics.id, topic_ids=[thermodynamics.id], weight=1.0)
    exam = ExamResponse(
        exam_id="exam_jee_main",
        code="JEE_MAIN",
        name="JEE Main",
        description="JEE Main core syllabus",
        syllabus=[syllabus_item],
        version="2024.1",
        is_active=True,
        metadata={"region": "IN"},
        created_by="system",
        created_at=now,
        updated_at=now,
    )
    db.insert_exam(exam)

    q1_options = [
        OptionSchema(id="opt1", content="Increase in internal energy", rationale="dU = Q at constant volume"),
        OptionSchema(id="opt2", content="Decrease in internal energy"),
        OptionSchema(id="opt3", content="No change in internal energy"),
        OptionSchema(id="opt4", content="Internal energy doubles"),
    ]
    q1 = QuestionResponse(
        question_id="q_thermo_1",
        question_type="MCQ",
        subject_id=physics.id,
        topic_ids=[thermodynamics.id],
        text="What happens to internal energy when heat is added at constant volume?",
        options=q1_options,
        correct_option_id="opt1",
        difficulty=2,
        target_exam_tags=["JEE_MAIN"],
        tags=["thermo", "first-law"],
        source="curated",
        version="1.0",
        metadata={"chapter": "First Law"},
        solution="Internal energy rises equal to heat added.",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.insert_question(q1)

    q2_options = [
        OptionSchema(id="optA", content="Temperature remains constant"),
        OptionSchema(id="optB", content="Pressure decreases"),
        OptionSchema(id="optC", content="Volume increases", rationale="Charles law at constant pressure"),
        OptionSchema(id="optD", content="Moles increase"),
    ]
    q2 = QuestionResponse(
        question_id="q_thermo_2",
        question_type="MCQ",
        subject_id=physics.id,
        topic_ids=[thermodynamics.id],
        text="In an isobaric expansion of an ideal gas, what happens to volume?",
        options=q2_options,
        correct_option_id="optC",
        difficulty=1,
        target_exam_tags=["JEE_MAIN"],
        tags=["gas-laws"],
        source="curated",
        version="1.0",
        metadata={"chapter": "Gas Laws"},
        solution="Volume increases in proportion to absolute temperature.",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.insert_question(q2)
