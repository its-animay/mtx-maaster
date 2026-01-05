from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi import Query

from app.db.session import Database, get_db
from app.schemas.master import (
    PaginatedSubjects,
    SubjectCreate,
    SubjectResponse,
    SubjectUpdate,
    TopicCreate,
    TopicResponse,
    TopicUpdate,
    TopicUpdateLinks,
)
from app.services.master_service import (
    create_subject,
    create_topic,
    delete_subject,
    delete_topic,
    get_subject,
    get_topic,
    list_subjects,
    list_topics,
    update_subject,
    update_topic,
    update_topic_links,
)

router = APIRouter()


@router.post("/subjects", response_model=SubjectResponse)
def create_subject_endpoint(subject: SubjectCreate, db: Database = Depends(get_db)) -> SubjectResponse:
    return create_subject(subject, db)


@router.get("/subjects", response_model=PaginatedSubjects)
def list_subjects_endpoint(
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    tags: Optional[List[str]] = Query(default=None),
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "name",
    sort_order: str = "asc",
    db: Database = Depends(get_db),
) -> PaginatedSubjects:
    return list_subjects(
        db=db,
        is_active=is_active,
        search=search,
        tags=tags,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
def get_subject_endpoint(subject_id: str, db: Database = Depends(get_db)) -> SubjectResponse:
    return get_subject(subject_id, db)


@router.put("/subjects/{subject_id}", response_model=SubjectResponse)
def update_subject_endpoint(
    subject_id: str, payload: SubjectUpdate, db: Database = Depends(get_db)
) -> SubjectResponse:
    return update_subject(subject_id, payload, db)


@router.delete("/subjects/{subject_id}")
def delete_subject_endpoint(subject_id: str, db: Database = Depends(get_db)) -> dict:
    delete_subject(subject_id, db)
    return {"status": "deleted", "subject_id": subject_id}


@router.post("/topics", response_model=TopicResponse)
def create_topic_endpoint(topic: TopicCreate, db: Database = Depends(get_db)) -> TopicResponse:
    return create_topic(topic, db)


@router.get("/topics", response_model=List[TopicResponse])
def list_topics_endpoint(subject_id: Optional[str] = None, db: Database = Depends(get_db)) -> List[TopicResponse]:
    return list_topics(subject_id, db)


@router.get("/topics/{topic_id}", response_model=TopicResponse)
def get_topic_endpoint(topic_id: str, db: Database = Depends(get_db)) -> TopicResponse:
    return get_topic(topic_id, db)


@router.put("/topics/{topic_id}", response_model=TopicResponse)
def update_topic_endpoint(
    topic_id: str, payload: TopicUpdate, db: Database = Depends(get_db)
) -> TopicResponse:
    return update_topic(topic_id, payload, db)


@router.patch("/topics/{topic_id}/links", response_model=TopicResponse)
def update_topic_links_endpoint(
    topic_id: str, payload: TopicUpdateLinks, db: Database = Depends(get_db)
) -> TopicResponse:
    return update_topic_links(
        topic_id,
        related_topic_ids=payload.related_topic_ids,
        prerequisite_topic_ids=payload.prerequisite_topic_ids,
        db=db,
    )


@router.delete("/topics/{topic_id}")
def delete_topic_endpoint(topic_id: str, db: Database = Depends(get_db)) -> dict:
    delete_topic(topic_id, db)
    return {"status": "deleted", "topic_id": topic_id}
