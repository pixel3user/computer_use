from datetime import datetime
from pathlib import Path

import pytest

from naukri_apply.models import (
    ApplicationResult,
    ApplicationStatus,
    ApplyType,
    JobListing,
    UserProfile,
)


class TestUserProfile:
    def test_valid_user_profile(self, sample_user_profile):
        assert sample_user_profile.name == "Test User"
        assert sample_user_profile.email == "test@example.com"
        assert sample_user_profile.phone == "+91-9876543210"
        assert sample_user_profile.resume_path == Path("./resume.pdf")

    def test_user_profile_optional_fields(self):
        profile = UserProfile(
            name="Minimal User",
            email="min@example.com",
            phone="1234567890",
            resume_path=Path("resume.pdf"),
        )
        assert profile.linkedin_url is None
        assert profile.experience_years is None
        assert profile.current_company is None

    def test_invalid_email_raises_error(self):
        with pytest.raises(Exception):
            UserProfile(
                name="Bad Email",
                email="not-an-email",
                phone="1234567890",
                resume_path=Path("resume.pdf"),
            )


class TestJobListing:
    def test_job_listing_creation(self, sample_job_listing):
        assert sample_job_listing.company_name == "Acme Inc"
        assert sample_job_listing.job_title == "Senior Python Developer"
        assert sample_job_listing.location == "Bangalore"
        assert sample_job_listing.url == "https://www.naukri.com/job-listings-12345"
        assert sample_job_listing.apply_type == ApplyType.EASY_APPLY


class TestApplyType:
    def test_enum_values(self):
        assert ApplyType.EASY_APPLY.value == "easy_apply"
        assert ApplyType.EXTERNAL.value == "external"
        assert ApplyType.UNKNOWN.value == "unknown"


class TestApplicationStatus:
    def test_enum_values(self):
        assert ApplicationStatus.APPLIED.value == "applied"
        assert ApplicationStatus.FAILED.value == "failed"
        assert ApplicationStatus.SKIPPED.value == "skipped"
        assert ApplicationStatus.EXTERNAL_PARTIAL.value == "external_partial"


class TestApplicationResult:
    def test_auto_generates_timestamp(self, sample_job_listing):
        before = datetime.now()
        result = ApplicationResult(
            job=sample_job_listing,
            status=ApplicationStatus.APPLIED,
        )
        after = datetime.now()

        assert result.timestamp is not None
        assert before <= result.timestamp <= after

    def test_with_explicit_timestamp(self, sample_job_listing):
        ts = datetime(2024, 1, 15, 10, 30, 0)
        result = ApplicationResult(
            job=sample_job_listing,
            status=ApplicationStatus.FAILED,
            timestamp=ts,
            notes="Connection timeout",
        )

        assert result.timestamp == ts
        assert result.notes == "Connection timeout"

    def test_notes_default_none(self, sample_job_listing):
        result = ApplicationResult(
            job=sample_job_listing,
            status=ApplicationStatus.SKIPPED,
        )
        assert result.notes is None
