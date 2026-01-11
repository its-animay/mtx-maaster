from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class InstructionBlock(BaseModel):
    """A titled block of bullet instructions."""

    title: str
    description: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)


class ProctoringRules(BaseModel):
    """Test-time security and proctoring requirements."""

    proctoring_mode: str = "none"  # none | ai | human | browser
    tab_switch_limit: Optional[int] = None
    fullscreen_required: bool = False
    copy_paste_allowed: bool = False
    right_click_allowed: bool = False
    camera_required: bool = False
    microphone_required: bool = False
    identity_verification_required: bool = False
    notes: Optional[str] = None


class TestInstructionsBase(BaseModel):
    """Shared fields for test instructions."""

    summary: Optional[str] = None
    sections: List[InstructionBlock] = Field(default_factory=list)
    proctoring: Optional[ProctoringRules] = None
    metadata: Optional[Dict[str, Any]] = None


class TestInstructionsCreate(TestInstructionsBase):
    """Payload to create or replace instructions for a test."""

    pass


class TestInstructionsResponse(TestInstructionsBase):
    """Stored instructions document."""

    instruction_id: str
    test_id: str
    created_at: datetime
    updated_at: datetime
