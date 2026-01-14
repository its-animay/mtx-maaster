from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Request, Depends, HTTPException, status, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from app.db.session import get_db, Database
from app.schemas.master import SubjectCreate, TopicCreate
from app.schemas.question import QuestionResponse, QuestionType, OptionSchema
from app.services.master_service import create_subject, create_topic
import uuid
import json

web_router = APIRouter()
templates = Jinja2Templates(directory="templates")


def parse_json_field(json_str: Optional[str]) -> Optional[dict]:
    """Parses JSON string field, returns None if empty. Raises ValueError if invalid."""
    if not json_str or not json_str.strip():
        return None
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")


def parse_list_field(list_str: Optional[str]) -> List[str]:
    """Splits comma-separated string into a list of stripped strings."""
    if not list_str:
        return []
    return [item.strip() for item in list_str.split(",") if item.strip()]


@web_router.get("/", include_in_schema=False)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@web_router.get("/subjects")
async def read_subjects(request: Request, db: Database = Depends(get_db)):
    subjects, _ = db.list_subjects(is_active=True, limit=100)
    return templates.TemplateResponse("subjects.html", {"request": request, "subjects": subjects})


# --- Admin Routes ---

@web_router.get("/admin", include_in_schema=False)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse("admin/index.html", {"request": request})


# Subject Creation
@web_router.get("/admin/subjects/create", include_in_schema=False)
async def create_subject_form(request: Request):
    return templates.TemplateResponse("admin/create_subject.html", {"request": request})


@web_router.post("/admin/subjects/create", include_in_schema=False)
async def create_subject_action(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    description: str = Form(None),
    tags: str = Form(None),
    metadata: str = Form(None),
    is_active: bool = Form(False),  # Checkbox not sent if unchecked
    db: Database = Depends(get_db)
):
    try:
        tags_list = parse_list_field(tags)
        metadata_dict = parse_json_field(metadata)

        subject_in = SubjectCreate(
            name=name,
            slug=slug,
            description=description,
            tags=tags_list,
            metadata=metadata_dict,
            is_active=is_active
        )
        create_subject(subject_in, db=db)
        return templates.TemplateResponse("admin/base_admin.html", {
            "request": request,
            "SUCCESS_MSG": f"Subject '{name}' created successfully!"
        })
    except Exception as e:
        return templates.TemplateResponse("admin/create_subject.html", {
            "request": request,
            "ERROR_MSG": str(e)
            # Ideally we'd pass back form values here to preserve input
        })


# Topic Creation
@web_router.get("/admin/topics/create", include_in_schema=False)
async def create_topic_form(request: Request, db: Database = Depends(get_db)):
    subjects, _ = db.list_subjects(limit=1000)
    return templates.TemplateResponse("admin/create_topic.html", {"request": request, "subjects": subjects})


@web_router.post("/admin/topics/create", include_in_schema=False)
async def create_topic_action(
    request: Request,
    subject_id: str = Form(...),
    name: str = Form(...),
    slug: str = Form(...),
    difficulty_weight: float = Form(...),
    description: str = Form(None),
    bloom_level: str = Form(None),
    related_topic_ids: str = Form(None),
    prerequisite_topic_ids: str = Form(None),
    tags: str = Form(None),
    metadata: str = Form(None),
    is_active: bool = Form(False),
    db: Database = Depends(get_db)
):
    try:
        related_ids_list = parse_list_field(related_topic_ids)
        prereq_ids_list = parse_list_field(prerequisite_topic_ids)
        tags_list = parse_list_field(tags)
        metadata_dict = parse_json_field(metadata)

        topic_in = TopicCreate(
            subject_id=subject_id,
            name=name,
            slug=slug,
            difficulty_weight=difficulty_weight,
            description=description,
            bloom_level=bloom_level,
            related_topic_ids=related_ids_list,
            prerequisite_topic_ids=prereq_ids_list,
            tags=tags_list,
            metadata=metadata_dict,
            is_active=is_active
        )
        create_topic(topic_in, db=db)
        # Fetch subjects again for re-rendering if we wanted to stay on page, but here we show success on base
        return templates.TemplateResponse("admin/base_admin.html", {
            "request": request,
            "SUCCESS_MSG": f"Topic '{name}' created successfully!"
        })
    except Exception as e:
        subjects, _ = db.list_subjects(limit=1000)
        return templates.TemplateResponse("admin/create_topic.html", {
            "request": request,
            "ERROR_MSG": str(e),
            "subjects": subjects
        })


# Question Creation
@web_router.get("/admin/questions/create", include_in_schema=False)
async def create_question_form(request: Request, db: Database = Depends(get_db)):
    subjects, _ = db.list_subjects(limit=1000)
    topics = db.list_topics() # Fetch all topics, filtering is done via JS for MVP
    return templates.TemplateResponse("admin/create_question.html", {
        "request": request,
        "subjects": subjects,
        "topics": topics
    })



@web_router.post("/admin/questions/create", include_in_schema=False)
async def create_question_action(
    request: Request,
    subject_id: str = Form(...),
    topic_id: str = Form(...),
    question_type: str = Form(...),
    text: str = Form(...),
    difficulty: int = Form(...),
    # MCQ/MSQ fields
    option_a: Optional[str] = Form(None),
    option_b: Optional[str] = Form(None),
    option_c: Optional[str] = Form(None),
    option_d: Optional[str] = Form(None),
    correct_option_id_select: Optional[str] = Form(None), # For MCQ
    correct_option_ids: Optional[List[str]] = Form(None), # For MSQ (multi-select)
    # NAT fields
    answer_value: Optional[str] = Form(None),
    # Optional Fields
    target_exam_tags: str = Form(None),
    tags: str = Form(None),
    source: str = Form(None),
    version: str = Form(None),
    solution: str = Form(None),
    metadata: str = Form(None),
    is_active: bool = Form(False),
    db: Database = Depends(get_db)
):
    try:
        options = []
        correct_opt_id = None # for MCQ
        correct_opt_ids_list = None # for MSQ
        ans_val = None

        # Build options if applicable
        if question_type in ("MCQ", "MSQ"):
            # Simple validation: ensure at least one option if creating new
            if option_a: options.append(OptionSchema(id="opt_a", content=option_a))
            if option_b: options.append(OptionSchema(id="opt_b", content=option_b))
            if option_c: options.append(OptionSchema(id="opt_c", content=option_c))
            if option_d: options.append(OptionSchema(id="opt_d", content=option_d))
        
        if question_type == "MCQ":
            correct_opt_id = correct_option_id_select
        elif question_type == "MSQ":
            # correct_option_ids form list comes from multiple select or checkboxes
            # If using checkboxes with same name, FastAPI/Starlette Form parsing gets list? 
            # Actually standard Form(...) might get only last value if not typed List.
            # Let's assume we handle it via parse_list_field if it comes as comma string, 
            # Or reliance on FastAPI's List[str] support for same-key inputs.
            # However, simpler for manual text input or multi-select is just list.
            # Let's assume correct_option_ids is passed as list from multi-select.
             if correct_option_ids:
                 correct_opt_ids_list = correct_option_ids
        elif question_type == "NAT":
            ans_val = answer_value

        # Parse Opts
        target_exams_list = parse_list_field(target_exam_tags)
        tags_list = parse_list_field(tags)
        metadata_dict = parse_json_field(metadata)

        now = datetime.utcnow()
        question = QuestionResponse(
            question_id=f"q_{uuid.uuid4()}",
            question_type=QuestionType(question_type),
            subject_id=subject_id,
            topic_ids=[topic_id],
            text=text,
            options=options,
            correct_option_id=correct_opt_id,
            correct_option_ids=correct_opt_ids_list,
            answer_value=ans_val,
            difficulty=difficulty,
            target_exam_tags=target_exams_list,
            tags=tags_list,
            source=source,
            version=version,
            solution=solution,
            metadata=metadata_dict,
            is_active=is_active,
            created_at=now,
            updated_at=now
        )
        
        db.insert_question(question)

        return templates.TemplateResponse("admin/base_admin.html", {
            "request": request,
            "SUCCESS_MSG": "Question created successfully!"
        })

    except Exception as e:
        subjects, _ = db.list_subjects(limit=1000)
        topics = db.list_topics()
        return templates.TemplateResponse("admin/create_question.html", {
            "request": request,
            "ERROR_MSG": str(e),
            "subjects": subjects,
            "topics": topics
        })
