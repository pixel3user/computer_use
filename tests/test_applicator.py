"""Tests for JobApplicator metadata extraction."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from naukri_apply.applicator import JobApplicator
from naukri_apply.models import ApplyType


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.headless = True
    config.slow_mo = 0
    return config


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.goto = AsyncMock()
    return page


class TestJobApplicator:
    """Test job page metadata extraction."""

    @pytest.mark.asyncio
    async def test_extract_job_title(self, mock_page, mock_config):
        """Test that job title is extracted from page selectors."""
        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_element.text_content = AsyncMock(return_value="Senior Python Developer")

        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_element))

        applicator = JobApplicator(mock_page, mock_config)
        title = await applicator._extract_job_title()
        assert title == "Senior Python Developer"

    @pytest.mark.asyncio
    async def test_extract_job_title_returns_unknown_when_not_found(self, mock_page, mock_config):
        """Test fallback to 'Unknown' when no title element found."""
        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(return_value=False)

        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_element))

        applicator = JobApplicator(mock_page, mock_config)
        title = await applicator._extract_job_title()
        assert title == "Unknown"

    @pytest.mark.asyncio
    async def test_extract_company_name(self, mock_page, mock_config):
        """Test company name extraction."""
        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_element.text_content = AsyncMock(return_value="Acme Corp")

        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_element))

        applicator = JobApplicator(mock_page, mock_config)
        name = await applicator._extract_company_name()
        assert name == "Acme Corp"

    @pytest.mark.asyncio
    async def test_extract_company_returns_unknown_when_not_found(self, mock_page, mock_config):
        """Test fallback for company name."""
        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(return_value=False)

        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_element))

        applicator = JobApplicator(mock_page, mock_config)
        name = await applicator._extract_company_name()
        assert name == "Unknown"

    @pytest.mark.asyncio
    async def test_extract_location(self, mock_page, mock_config):
        """Test location extraction."""
        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_element.text_content = AsyncMock(return_value="Bangalore, India")

        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_element))

        applicator = JobApplicator(mock_page, mock_config)
        location = await applicator._extract_location()
        assert location == "Bangalore, India"

    @pytest.mark.asyncio
    async def test_extract_location_returns_unknown(self, mock_page, mock_config):
        """Test fallback for location."""
        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(return_value=False)

        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_element))

        applicator = JobApplicator(mock_page, mock_config)
        location = await applicator._extract_location()
        assert location == "Unknown"

    @pytest.mark.asyncio
    async def test_determine_apply_type_easy_apply(self, mock_page, mock_config):
        """Test detection of Easy Apply type."""
        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_element.get_attribute = AsyncMock(return_value=None)
        mock_element.text_content = AsyncMock(return_value="Easy Apply")

        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_element))

        applicator = JobApplicator(mock_page, mock_config)
        apply_type = await applicator._determine_apply_type()
        assert apply_type == ApplyType.EASY_APPLY

    @pytest.mark.asyncio
    async def test_determine_apply_type_external(self, mock_page, mock_config):
        """Test detection of external apply type."""
        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_element.get_attribute = AsyncMock(return_value="https://greenhouse.io/apply/123")
        mock_element.text_content = AsyncMock(return_value="Apply")

        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_element))

        applicator = JobApplicator(mock_page, mock_config)
        apply_type = await applicator._determine_apply_type()
        assert apply_type == ApplyType.EXTERNAL

    @pytest.mark.asyncio
    async def test_determine_apply_type_unknown_on_error(self, mock_page, mock_config):
        """Test that errors result in UNKNOWN apply type."""
        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(side_effect=Exception("Element not found"))

        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_element))

        applicator = JobApplicator(mock_page, mock_config)
        apply_type = await applicator._determine_apply_type()
        assert apply_type == ApplyType.UNKNOWN

    @pytest.mark.asyncio
    async def test_process_job_full_extraction(self, mock_page, mock_config):
        """Test complete job processing with all fields extracted."""
        call_count = {"count": 0}
        selectors_responses = {
            # Job title selectors
            ".jd-header-title": ("Senior Dev", True),
            "h1.jd-header-title": ("Senior Dev", True),
            # Company selectors
            ".jd-header-comp-name a": ("TestCo", True),
            ".company-name": ("TestCo", True),
            # Location selectors
            ".location": ("Mumbai", True),
            # Apply button
            "button:has-text('Apply'), a:has-text('Apply')": ("Apply", True),
        }

        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_element.text_content = AsyncMock(return_value="Senior Dev")
        mock_element.get_attribute = AsyncMock(return_value=None)

        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_element))

        applicator = JobApplicator(mock_page, mock_config)
        job = await applicator.process_job("https://www.naukri.com/job-12345")

        assert job.url == "https://www.naukri.com/job-12345"
        assert job.job_title == "Senior Dev"
        assert job.company_name == "Senior Dev"  # Same mock for all locators
        mock_page.goto.assert_called_once_with(
            "https://www.naukri.com/job-12345",
            timeout=30000,
            wait_until="domcontentloaded",
        )

    @pytest.mark.asyncio
    async def test_process_job_handles_missing_elements(self, mock_page, mock_config):
        """Test that missing elements result in 'Unknown' defaults."""
        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(return_value=False)
        mock_element.text_content = AsyncMock(return_value=None)
        mock_element.get_attribute = AsyncMock(return_value=None)

        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_element))

        applicator = JobApplicator(mock_page, mock_config)
        job = await applicator.process_job("https://www.naukri.com/job-99999")

        assert job.job_title == "Unknown"
        assert job.company_name == "Unknown"
        assert job.location == "Unknown"
        assert job.apply_type == ApplyType.UNKNOWN
