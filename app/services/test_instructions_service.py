import uuid
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status

from app.db.session import Database, get_db
from app.schemas.test_instructions import TestInstructionsCreate, TestInstructionsResponse
from app.services.test_service import _get_test


def upsert_test_instructions(test_id: str, payload: TestInstructionsCreate, db: Optional[Database] = None) -> TestInstructionsResponse:
    """Create or replace instructions for a test. Returns the stored document."""
    db = db or get_db()
    # Ensure test exists (and is active)
    _get_test(test_id, db)

    existing = db.get_test_instructions(test_id)
    now = datetime.utcnow()
    instruction_id = existing.instruction_id if existing else f"instr_{uuid.uuid4()}"

    record = TestInstructionsResponse(
        instruction_id=instruction_id,
        test_id=test_id,
        summary=payload.summary,
        sections=payload.sections,
        proctoring=payload.proctoring,
        metadata=payload.metadata,
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )
    db.upsert_test_instructions(record)
    return record


def get_test_instructions(test_id: str, db: Optional[Database] = None) -> TestInstructionsResponse:
    """Fetch instructions for a test; 404 if missing."""
    db = db or get_db()
    _get_test(test_id, db)
    doc = db.get_test_instructions(test_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructions not found for test")
    return doc
