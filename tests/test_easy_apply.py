"""Tests for EasyApplyHandler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from naukri_apply.easy_apply import EasyApplyHandler
from naukri_apply.models import ApplyType, ApplicationStatus, JobListing


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.headless = True
    config.slow_mo = 0
    config.user_profile = MagicMock()
    config.user_profile.name = "Test User"
    config.user_profile.email = "test@example.com"
    config.user_profile.experience_years = 5
    return config


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.wait_for_timeout = AsyncMock()
    return page


@pytest.fixture
def sample_job():
    return JobListing(
        company_name="TestCo",
        job_title="Engineer",
        location="Mumbai",
        url="https://www.naukri.com/job-12345",
        apply_type=ApplyType.EASY_APPLY,
    )


class TestEasyApplyHandler:
    """Tests for EasyApplyHandler apply logic."""

    @pytest.mark.asyncio
    async def test_apply_success(self, mock_page, mock_config, sample_job):
        """Test successful Easy Apply flow."""
        # Mock apply button found and visible
        mock_button = MagicMock()
        mock_button.is_visible = AsyncMock(return_value=True)
        mock_button.click = AsyncMock()

        # First call returns apply button, subsequent calls return success indicator
        call_count = {"n": 0}

        def locator_side_effect(selector):
            mock_loc = MagicMock()
            if "Apply" in selector:
                mock_loc.first = mock_button
            else:
                # Success indicator
                success_el = MagicMock()
                success_el.is_visible = AsyncMock(return_value=True)
                mock_loc.first = success_el
            return mock_loc

        mock_page.locator = MagicMock(side_effect=locator_side_effect)

        handler = EasyApplyHandler(mock_page, mock_config)
        result = await handler.apply(sample_job)

        assert result.status == ApplicationStatus.APPLIED
        assert "successfully" in result.notes.lower()

    @pytest.mark.asyncio
    async def test_apply_button_not_found(self, mock_page, mock_config, sample_job):
        """Test failure when apply button is not found."""
        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(return_value=False)

        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_element))

        handler = EasyApplyHandler(mock_page, mock_config)
        result = await handler.apply(sample_job)

        assert result.status == ApplicationStatus.FAILED
        assert "not found" in result.notes.lower()

    @pytest.mark.asyncio
    async def test_apply_no_success_confirmation(self, mock_page, mock_config, sample_job):
        """Test failure when no success confirmation appears."""
        mock_button = MagicMock()
        mock_button.is_visible = AsyncMock(return_value=True)
        mock_button.click = AsyncMock()

        # All locators return not visible (no success indicator)
        mock_not_visible = MagicMock()
        mock_not_visible.is_visible = AsyncMock(return_value=False)

        call_count = {"n": 0}

        def locator_side_effect(selector):
            call_count["n"] += 1
            mock_loc = MagicMock()
            # First few calls are for apply button selectors
            if call_count["n"] <= 6:
                if call_count["n"] == 1:
                    mock_loc.first = mock_button
                else:
                    mock_loc.first = mock_not_visible
            else:
                # Success indicators - all not visible
                mock_loc.first = mock_not_visible
            return mock_loc

        mock_page.locator = MagicMock(side_effect=locator_side_effect)

        handler = EasyApplyHandler(mock_page, mock_config)
        result = await handler.apply(sample_job)

        assert result.status == ApplicationStatus.FAILED
        assert "could not confirm" in result.notes.lower()

    @pytest.mark.asyncio
    async def test_apply_exception_returns_failed(self, mock_page, mock_config, sample_job):
        """Test that an exception during apply returns FAILED status."""
        mock_page.locator = MagicMock(side_effect=Exception("Browser crashed"))

        handler = EasyApplyHandler(mock_page, mock_config)
        result = await handler.apply(sample_job)

        assert result.status == ApplicationStatus.FAILED
        assert "not found" in result.notes.lower()

    @pytest.mark.asyncio
    async def test_handle_screening_questions_radio(self, mock_page, mock_config):
        """Test that screening questions with radio buttons are handled."""
        mock_radio = MagicMock()
        mock_radio.count = AsyncMock(return_value=2)
        mock_radio.first = MagicMock()
        mock_radio.first.check = AsyncMock()

        mock_select = MagicMock()
        mock_select.count = AsyncMock(return_value=0)

        mock_submit_btn = MagicMock()
        mock_submit_btn.is_visible = AsyncMock(return_value=False)

        def locator_side_effect(selector):
            if "radio" in selector:
                return mock_radio
            elif selector == "select":
                return mock_select
            else:
                return MagicMock(first=mock_submit_btn)

        mock_page.locator = MagicMock(side_effect=locator_side_effect)

        handler = EasyApplyHandler(mock_page, mock_config)
        # Should not raise
        await handler._handle_screening_questions()

        mock_radio.first.check.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_apply_button_tries_multiple_selectors(self, mock_page, mock_config):
        """Test that _find_apply_button iterates through selectors."""
        call_count = {"n": 0}

        def locator_side_effect(selector):
            call_count["n"] += 1
            mock_loc = MagicMock()
            if call_count["n"] == 3:
                # Third selector matches
                visible_el = MagicMock()
                visible_el.is_visible = AsyncMock(return_value=True)
                mock_loc.first = visible_el
            else:
                not_visible_el = MagicMock()
                not_visible_el.is_visible = AsyncMock(return_value=False)
                mock_loc.first = not_visible_el
            return mock_loc

        mock_page.locator = MagicMock(side_effect=locator_side_effect)

        handler = EasyApplyHandler(mock_page, mock_config)
        result = await handler._find_apply_button()

        assert result is not None
        assert call_count["n"] == 3

    @pytest.mark.asyncio
    async def test_screening_questions_use_llm_when_available(self, mock_page, mock_config):
        """Test that screening questions use LLM when llm_agent is available."""
        mock_llm_agent = MagicMock()
        mock_llm_agent.answer_screening_question = AsyncMock(return_value="5+ years")

        # Mock radio buttons
        mock_radio = MagicMock()
        mock_radio.count = AsyncMock(return_value=2)
        mock_radio.first = MagicMock()
        mock_radio.first.check = AsyncMock()
        mock_radio.first.locator = MagicMock()
        mock_radio.nth = MagicMock()

        mock_parent = MagicMock()
        mock_parent.inner_text = AsyncMock(return_value="How many years of experience?")

        # radio button label extraction
        radio_0 = MagicMock()
        radio_0.evaluate = AsyncMock(return_value="0-2 years")
        radio_0.check = AsyncMock()
        radio_1 = MagicMock()
        radio_1.evaluate = AsyncMock(return_value="5+ years")
        radio_1.check = AsyncMock()

        mock_radio.nth = MagicMock(side_effect=lambda i: [radio_0, radio_1][i])

        mock_select = MagicMock()
        mock_select.count = AsyncMock(return_value=0)

        mock_submit_btn = MagicMock()
        mock_submit_btn.is_visible = AsyncMock(return_value=False)

        def locator_side_effect(selector):
            if "radio" in selector:
                result = mock_radio
                result.first = MagicMock()
                result.first.check = AsyncMock()
                result.first.locator = MagicMock(return_value=mock_parent)
                return result
            elif selector == "select":
                return mock_select
            else:
                return MagicMock(first=mock_submit_btn)

        mock_page.locator = MagicMock(side_effect=locator_side_effect)

        handler = EasyApplyHandler(mock_page, mock_config, llm_agent=mock_llm_agent)
        await handler._handle_screening_questions()

        # Verify LLM was consulted
        mock_llm_agent.answer_screening_question.assert_called_once()

    @pytest.mark.asyncio
    async def test_screening_questions_fallback_without_llm(self, mock_page, mock_config):
        """Test that screening questions fall back to heuristic when no LLM."""
        mock_radio = MagicMock()
        mock_radio.count = AsyncMock(return_value=2)
        mock_radio.first = MagicMock()
        mock_radio.first.check = AsyncMock()

        mock_select = MagicMock()
        mock_select.count = AsyncMock(return_value=0)

        mock_submit_btn = MagicMock()
        mock_submit_btn.is_visible = AsyncMock(return_value=False)

        def locator_side_effect(selector):
            if "radio" in selector:
                return mock_radio
            elif selector == "select":
                return mock_select
            else:
                return MagicMock(first=mock_submit_btn)

        mock_page.locator = MagicMock(side_effect=locator_side_effect)

        # No LLM agent provided
        handler = EasyApplyHandler(mock_page, mock_config, llm_agent=None)
        await handler._handle_screening_questions()

        # Should fall back to selecting first radio button
        mock_radio.first.check.assert_called_once()
