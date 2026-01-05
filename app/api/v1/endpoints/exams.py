from typing import List

from fastapi import APIRouter, Depends

from app.db.session import Database, get_db
from app.schemas.exam import ExamCreate, ExamResponse, ExamSyllabusItem, ExamUpdate
from app.services.exam_service import create_exam, delete_exam, get_exam, get_exam_syllabus, list_exams, update_exam

router = APIRouter()


@router.post("/exams", response_model=ExamResponse)
def create_exam_endpoint(payload: ExamCreate, db: Database = Depends(get_db)) -> ExamResponse:
    return create_exam(payload, db)


@router.get("/exams", response_model=List[ExamResponse])
def list_exams_endpoint(active_only: bool = False, db: Database = Depends(get_db)) -> List[ExamResponse]:
    return list_exams(db, active_only=active_only)


@router.get("/exams/{exam_id}", response_model=ExamResponse)
def get_exam_endpoint(exam_id: str, db: Database = Depends(get_db)) -> ExamResponse:
    return get_exam(exam_id, db)


@router.put("/exams/{exam_id}", response_model=ExamResponse)
def update_exam_endpoint(
    exam_id: str, payload: ExamUpdate, db: Database = Depends(get_db)
) -> ExamResponse:
    return update_exam(exam_id, payload, db)


@router.delete("/exams/{exam_id}")
def delete_exam_endpoint(exam_id: str, db: Database = Depends(get_db)) -> dict:
    delete_exam(exam_id, db)
    return {"status": "deleted", "exam_id": exam_id}


@router.get("/exams/{exam_id}/syllabus", response_model=List[ExamSyllabusItem])
def get_exam_syllabus_endpoint(exam_id: str, db: Database = Depends(get_db)) -> List[ExamSyllabusItem]:
    return get_exam_syllabus(exam_id, db)
