import hashlib
import random
from typing import Any, Dict, List, Optional, Tuple

from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection

from app.db.session import get_db


def _normalize_seed(seed: str) -> float:
    """Convert arbitrary seed to float in [0,1)."""

    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    return int(digest, 16) / float(2**128)


class QuestionRepo:
    """Mongo-backed repository for display-ready question documents."""

    def __init__(self, collection: Optional[Collection] = None) -> None:
        db = get_db()
        self.collection = collection or db.db["questions"]

    def insert(self, doc: Dict[str, Any]) -> None:
        self.collection.insert_one(doc)

    def update(self, question_id: str, patch: Dict[str, Any]) -> None:
        self.collection.update_one({"_id": question_id}, {"$set": patch})

    def find_by_id(self, question_id: str, projection: Optional[Dict[str, int]] = None) -> Optional[Dict[str, Any]]:
        return self.collection.find_one({"_id": question_id}, projection)

    def find_many(
        self,
        filters: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None,
        sort: Optional[List[Tuple[str, int]]] = None,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        include_score: bool = False,
    ) -> List[Dict[str, Any]]:
        query = dict(filters)
        if search:
            query["$text"] = {"$search": search}
        project = dict(projection or {})
        if include_score:
            project["score"] = {"$meta": "textScore"}
        cursor = self.collection.find(query, project)
        sort_fields: List[Tuple[str, Any]] = []
        if include_score:
            sort_fields.append(("score", {"$meta": "textScore"}))
        if sort:
            sort_fields.extend(sort)
        if sort_fields:
            cursor = cursor.sort(sort_fields)
        if skip:
            cursor = cursor.skip(max(0, skip))
        if limit:
            cursor = cursor.limit(max(0, limit))
        return list(cursor)

    def count(self, filters: Dict[str, Any], search: Optional[str] = None) -> int:
        query = dict(filters)
        if search:
            query["$text"] = {"$search": search}
        return self.collection.count_documents(query)

    def sample(self, filters: Dict[str, Any], limit: int, seed: Optional[str] = None) -> List[Dict[str, Any]]:
        if seed:
            seed_value = _normalize_seed(seed)
            first = list(
                self.collection.find(
                    {**filters, "rand_key": {"$gte": seed_value}},
                )
                .sort([("rand_key", ASCENDING)])
                .limit(limit)
            )
            remaining = limit - len(first)
            if remaining <= 0:
                return first
            wrap = list(
                self.collection.find({**filters, "rand_key": {"$lt": seed_value}})
                .sort([("rand_key", ASCENDING)])
                .limit(remaining)
            )
            return first + wrap

        pipeline: List[Dict[str, Any]] = [{"$match": filters}, {"$sample": {"size": max(0, limit)}}]
        return list(self.collection.aggregate(pipeline))


class InMemoryQuestionRepo(QuestionRepo):
    """Simple in-memory repo for unit tests."""

    def __init__(self) -> None:
        self.storage: Dict[str, Dict[str, Any]] = {}

    def insert(self, doc: Dict[str, Any]) -> None:
        self.storage[doc["_id"]] = dict(doc)

    def update(self, question_id: str, patch: Dict[str, Any]) -> None:
        if question_id not in self.storage:
            return
        self.storage[question_id].update(patch)

    def find_by_id(self, question_id: str, projection: Optional[Dict[str, int]] = None) -> Optional[Dict[str, Any]]:
        doc = self.storage.get(question_id)
        if not doc:
            return None
        return self._apply_projection(doc, projection)

    def find_many(
        self,
        filters: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None,
        sort: Optional[List[Tuple[str, int]]] = None,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        include_score: bool = False,
    ) -> List[Dict[str, Any]]:
        docs = []
        for doc in self.storage.values():
            if self._match(doc, filters, search):
                docs.append(self._apply_projection(doc, projection))
        if include_score and search:
            for d in docs:
                d["score"] = d.get("search_blob", "").count(search.lower())
            docs.sort(key=lambda x: (-x.get("score", 0), x.get("created_at"), x.get("_id")))
        if sort:
            for field, direction in reversed(sort):
                docs.sort(key=lambda x, f=field: x.get(f), reverse=direction == DESCENDING)
        if skip:
            docs = docs[skip:]
        if limit:
            docs = docs[:limit]
        return docs

    def count(self, filters: Dict[str, Any], search: Optional[str] = None) -> int:
        return len([1 for doc in self.storage.values() if self._match(doc, filters, search)])

    def sample(self, filters: Dict[str, Any], limit: int, seed: Optional[str] = None) -> List[Dict[str, Any]]:
        docs = [self._apply_projection(doc, None) for doc in self.storage.values() if self._match(doc, filters, None)]
        if seed:
            random.seed(seed)
        random.shuffle(docs)
        return docs[:limit]

    @staticmethod
    def _apply_projection(doc: Dict[str, Any], projection: Optional[Dict[str, int]]) -> Dict[str, Any]:
        if projection is None:
            return dict(doc)
        result = {}
        include_fields = {k for k, v in projection.items() if v}
        exclude_fields = {k for k, v in projection.items() if not v}
        if include_fields:
            for key in include_fields:
                if key in doc:
                    result[key] = doc[key]
        else:
            result = dict(doc)
            for key in exclude_fields:
                result.pop(key, None)
        return result

    @staticmethod
    def _get_value(doc: Dict[str, Any], dotted_key: str) -> Any:
        parts = dotted_key.split(".")
        current: Any = doc
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    @classmethod
    def _match(cls, doc: Dict[str, Any], filters: Dict[str, Any], search: Optional[str]) -> bool:
        for key, expected in filters.items():
            value = cls._get_value(doc, key)
            if value is None:
                return False
            if isinstance(expected, dict):
                if "$gte" in expected and value < expected["$gte"]:
                    return False
                if "$lte" in expected and value > expected["$lte"]:
                    return False
                if "$in" in expected:
                    if isinstance(value, list):
                        if not set(value).intersection(set(expected["$in"])):
                            return False
                    else:
                        if value not in expected["$in"]:
                            return False
                if "$elemMatch" in expected:
                    target = expected["$elemMatch"]
                    if not isinstance(value, list):
                        return False
                    if not any(item in target.get("$in", []) for item in value):
                        return False
                continue
            if isinstance(value, list):
                if expected not in value and value != expected:
                    return False
            elif value != expected:
                return False
        if search:
            blob = str(doc.get("search_blob", "")).lower()
            if search.lower() not in blob:
                return False
        return True


def get_question_repo() -> QuestionRepo:
    """Return a repo bound to the shared Database instance."""

    return QuestionRepo()
