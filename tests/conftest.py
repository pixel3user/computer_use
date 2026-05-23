import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml


@pytest.fixture
def sample_user_profile():
    from naukri_apply.models import UserProfile

    return UserProfile(
        name="Test User",
        email="test@example.com",
        phone="+91-9876543210",
        resume_path=Path("./resume.pdf"),
        linkedin_url="https://linkedin.com/in/testuser",
        experience_years=5,
        current_company="Test Corp",
        current_designation="Software Engineer",
        notice_period="30 days",
    )


@pytest.fixture
def sample_job_listing():
    from naukri_apply.models import ApplyType, JobListing

    return JobListing(
        company_name="Acme Inc",
        job_title="Senior Python Developer",
        location="Bangalore",
        url="https://www.naukri.com/job-listings-12345",
        apply_type=ApplyType.EASY_APPLY,
    )


@pytest.fixture
def sample_config_yaml(tmp_path):
    config_data = {
        "user_profile": {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "+91-9876543210",
            "resume_path": "./resume.pdf",
        },
        "naukri_email": "naukri@example.com",
        "naukri_password": "secret123",
        "output_csv": "applications.csv",
        "headless": True,
        "slow_mo": 50,
        "user_data_dir": ".browser_data",
    }

    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    return config_file


@pytest.fixture
def tmp_csv_path(tmp_path):
    return tmp_path / "test_applications.csv"


@pytest.fixture
def mock_app_config(sample_user_profile):
    from naukri_apply.models import LLMConfig, QuotaConfig

    config = MagicMock()
    config.user_profile = sample_user_profile
    config.naukri_email = "naukri@example.com"
    config.naukri_password = "secret123"
    config.groq_api_key = "gsk_test_key"
    config.headless = True
    config.slow_mo = 50
    config.user_data_dir = Path(".browser_data")
    config.output_csv = Path("applications.csv")
    config.delay_between_applications = 5.0
    config.llm = LLMConfig()
    config.quota = QuotaConfig()
    return config
