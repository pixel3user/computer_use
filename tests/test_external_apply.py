"""Tests for ExternalApplyHandler."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from naukri_apply.external_apply import ExternalApplyHandler
from naukri_apply.models import ApplyType, ApplicationStatus, JobListing, UserProfile


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.headless = True
    config.slow_mo = 0
    config.signup_password = "TestPass123!"
    config.user_profile = UserProfile(
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
    return config


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.wait_for_timeout = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.url = "https://jobs.greenhouse.io/company/apply"
    mock_context = MagicMock()
    page.context = mock_context
    return page


@pytest.fixture
def sample_external_job():
    return JobListing(
        company_name="ExternalCo",
        job_title="Backend Developer",
        location="Delhi",
        url="https://www.naukri.com/job-67890",
        apply_type=ApplyType.EXTERNAL,
    )


class TestExternalApplyHandler:
    """Tests for ExternalApplyHandler logic."""

    def test_detect_platform_greenhouse(self, mock_page, mock_config):
        """Test Greenhouse platform detection."""
        handler = ExternalApplyHandler(mock_page, mock_config)
        assert handler._detect_platform("https://boards.greenhouse.io/company/jobs/123") == "greenhouse"

    def test_detect_platform_lever(self, mock_page, mock_config):
        """Test Lever platform detection."""
        handler = ExternalApplyHandler(mock_page, mock_config)
        assert handler._detect_platform("https://jobs.lever.co/company/123") == "lever"

    def test_detect_platform_workday(self, mock_page, mock_config):
        """Test Workday platform detection."""
        handler = ExternalApplyHandler(mock_page, mock_config)
        assert handler._detect_platform("https://company.workday.com/apply") == "workday"

    def test_detect_platform_unknown(self, mock_page, mock_config):
        """Test unknown platform returns None."""
        handler = ExternalApplyHandler(mock_page, mock_config)
        assert handler._detect_platform("https://company.example.com/careers") is None

    @pytest.mark.asyncio
    async def test_is_signup_form_detected(self, mock_page, mock_config):
        """Test signup form detection when indicators are present."""
        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(return_value=True)

        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_element))

        # Create a separate page for the method call
        external_page = MagicMock()
        external_page.locator = MagicMock(return_value=MagicMock(first=mock_element))

        handler = ExternalApplyHandler(mock_page, mock_config)
        result = await handler._is_signup_form(external_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_signup_form_not_detected(self, mock_page, mock_config):
        """Test signup form detection when no indicators are present."""
        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(return_value=False)

        external_page = MagicMock()
        external_page.locator = MagicMock(return_value=MagicMock(first=mock_element))

        handler = ExternalApplyHandler(mock_page, mock_config)
        result = await handler._is_signup_form(external_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_fill_signup_form_uses_config_password(self, mock_page, mock_config):
        """Test that signup form uses password from config, not hardcoded."""
        external_page = MagicMock()

        # Mock find_field to return locators for email and password
        mock_email_locator = MagicMock()
        mock_password_locator = MagicMock()

        async def mock_find_field(page, field_type):
            if field_type == "email":
                return mock_email_locator
            elif field_type == "password":
                return mock_password_locator
            return None

        with patch("naukri_apply.external_apply.find_field", side_effect=mock_find_field):
            with patch("naukri_apply.external_apply.fill_text_field", new_callable=AsyncMock) as mock_fill:
                handler = ExternalApplyHandler(mock_page, mock_config)
                await handler._fill_signup_form(external_page)

                # Verify password from config is used
                calls = mock_fill.call_args_list
                assert len(calls) == 2
                # First call fills email
                assert calls[0][0] == (mock_email_locator, "test@example.com")
                # Second call fills password from config
                assert calls[1][0] == (mock_password_locator, "TestPass123!")

    @pytest.mark.asyncio
    async def test_fill_signup_form_skips_password_when_not_configured(self, mock_page, mock_config):
        """Test that signup form skips password when not configured."""
        mock_config.signup_password = None
        external_page = MagicMock()

        mock_email_locator = MagicMock()
        mock_password_locator = MagicMock()

        async def mock_find_field(page, field_type):
            if field_type == "email":
                return mock_email_locator
            elif field_type == "password":
                return mock_password_locator
            return None

        with patch("naukri_apply.external_apply.find_field", side_effect=mock_find_field):
            with patch("naukri_apply.external_apply.fill_text_field", new_callable=AsyncMock) as mock_fill:
                handler = ExternalApplyHandler(mock_page, mock_config)
                await handler._fill_signup_form(external_page)

                # Only email should be filled, password skipped
                calls = mock_fill.call_args_list
                assert len(calls) == 1
                assert calls[0][0] == (mock_email_locator, "test@example.com")

    @pytest.mark.asyncio
    async def test_fill_application_form(self, mock_page, mock_config):
        """Test application form filling with user profile data."""
        external_page = MagicMock()

        mock_locators = {}
        for field in ["name", "email", "phone", "linkedin", "experience", "company"]:
            mock_locators[field] = MagicMock()

        async def mock_find_field(page, field_type):
            return mock_locators.get(field_type)

        with patch("naukri_apply.external_apply.find_field", side_effect=mock_find_field):
            with patch("naukri_apply.external_apply.fill_text_field", new_callable=AsyncMock) as mock_fill:
                with patch("naukri_apply.external_apply.upload_file", new_callable=AsyncMock):
                    handler = ExternalApplyHandler(mock_page, mock_config)
                    await handler._fill_application_form(external_page)

                    # Verify fields were filled
                    assert mock_fill.call_count >= 5  # name, email, phone, linkedin, experience, company

    @pytest.mark.asyncio
    async def test_apply_returns_external_partial_on_success(self, mock_page, mock_config, sample_external_job):
        """Test that successful external apply returns EXTERNAL_PARTIAL status."""
        # Mock the new page that opens
        new_page = MagicMock()
        new_page.wait_for_load_state = AsyncMock()
        new_page.url = "https://boards.greenhouse.io/company/jobs/123"
        new_page.close = AsyncMock()

        # Mock click_apply_and_get_new_page
        handler = ExternalApplyHandler(mock_page, mock_config)

        with patch.object(handler, "_click_apply_and_get_new_page", new_callable=AsyncMock, return_value=new_page):
            with patch.object(handler, "_is_signup_form", new_callable=AsyncMock, return_value=False):
                with patch.object(handler, "_fill_application_form", new_callable=AsyncMock):
                    with patch.object(handler, "_submit_form", new_callable=AsyncMock):
                        result = await handler.apply(sample_external_job)

        assert result.status == ApplicationStatus.EXTERNAL_PARTIAL
        assert "greenhouse" in result.notes.lower()

    @pytest.mark.asyncio
    async def test_apply_returns_failed_on_exception(self, mock_page, mock_config, sample_external_job):
        """Test that exceptions during apply return FAILED status."""
        handler = ExternalApplyHandler(mock_page, mock_config)

        with patch.object(
            handler, "_click_apply_and_get_new_page",
            new_callable=AsyncMock,
            side_effect=Exception("Connection timeout"),
        ):
            result = await handler.apply(sample_external_job)

        assert result.status == ApplicationStatus.FAILED
        assert "error" in result.notes.lower()

    @pytest.mark.asyncio
    async def test_submit_form_tries_selectors(self, mock_page, mock_config):
        """Test that submit form tries multiple selectors."""
        external_page = MagicMock()
        external_page.wait_for_timeout = AsyncMock()

        call_count = {"n": 0}

        def locator_side_effect(selector):
            call_count["n"] += 1
            mock_loc = MagicMock()
            if call_count["n"] == 2:
                # Second selector matches
                visible_el = MagicMock()
                visible_el.is_visible = AsyncMock(return_value=True)
                visible_el.click = AsyncMock()
                mock_loc.first = visible_el
            else:
                not_visible_el = MagicMock()
                not_visible_el.is_visible = AsyncMock(return_value=False)
                mock_loc.first = not_visible_el
            return mock_loc

        external_page.locator = MagicMock(side_effect=locator_side_effect)

        handler = ExternalApplyHandler(mock_page, mock_config)
        await handler._submit_form(external_page)

        # Should have tried at least 2 selectors
        assert call_count["n"] >= 2
