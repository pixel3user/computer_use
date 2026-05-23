from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserProfile(BaseModel):
    name: str
    email: EmailStr
    phone: str
    resume_path: Path
    linkedin_url: Optional[str] = None
    experience_years: Optional[int] = None
    current_company: Optional[str] = None
    current_designation: Optional[str] = None
    notice_period: Optional[str] = None


class ApplyType(str, Enum):
    EASY_APPLY = "easy_apply"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


class ApplicationStatus(str, Enum):
    APPLIED = "applied"
    FAILED = "failed"
    SKIPPED = "skipped"
    EXTERNAL_PARTIAL = "external_partial"


class JobListing(BaseModel):
    company_name: str
    job_title: str
    location: str
    url: str
    apply_type: ApplyType


class ApplicationResult(BaseModel):
    job: JobListing
    status: ApplicationStatus
    timestamp: datetime = None
    notes: Optional[str] = None

    def __init__(self, **data):
        if data.get("timestamp") is None:
            data["timestamp"] = datetime.now()
        super().__init__(**data)
