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


class LLMConfig(BaseModel):
    model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    max_tokens: int = 4096
    temperature: float = 0.2
    max_steps: int = 50
    max_steps_dry_run: int = 10


class QuotaConfig(BaseModel):
    max_naukri_applications: int = 50
    enable_direct_apply: bool = True


class ApplyType(str, Enum):
    EASY_APPLY = "easy_apply"
    EXTERNAL = "external"
    DIRECT = "direct"
    UNKNOWN = "unknown"


class ApplicationStatus(str, Enum):
    APPLIED = "applied"
    FAILED = "failed"
    SKIPPED = "skipped"
    EXTERNAL_PARTIAL = "external_partial"
    DIRECT_APPLIED = "direct_applied"


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
