"""Tests for DirectApplyHandler class."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from naukri_apply.direct_apply import DirectApplyHandler
from naukri_apply.models import ApplyType, ApplicationStatus, JobListing


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.user_profile = MagicMock()
    config.user_profile.name = "Test User"
    config.user_profile.email = "test@example.com"
    return config


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.locator = MagicMock()
    return page


@pytest.fixture
def mock_llm_agent():
    agent = MagicMock()
    agent.find_company_career_page = AsyncMock(return_value="TestCo Software Engineer careers apply")
    agent.navigate_and_apply_direct = AsyncMock(return_value=True)
    return agent


@pytest.fixture
def sample_job():
    return JobListing(
        company_name="TestCo",
        job_title="Software Engineer",
        location="Bangalore",
        url="https://www.naukri.com/job-12345",
        apply_type=ApplyType.EASY_APPLY,
    )


class TestDirectApplyHandler:
    """Tests for DirectApplyHandler."""

    @pytest.mark.asyncio
    async def test_successful_direct_apply_returns_direct_applied(
        self, mock_page, mock_config, mock_llm_agent, sample_job
    ):
        """Test that a successful direct apply flow returns DIRECT_APPLIED status."""
        # Mock search results page - clicking works
        mock_link = MagicMock()
        mock_link.get_attribute = AsyncMock(return_value="https://testco.com/careers")
        mock_link.inner_text = AsyncMock(return_value="TestCo Careers")
        mock_link.click = AsyncMock()

        mock_results = MagicMock()
        mock_results.count = AsyncMock(return_value=1)
        mock_results.nth = MagicMock(return_value=mock_link)

        mock_page.locator = MagicMock(return_value=mock_results)

        handler = DirectApplyHandler(mock_page, mock_config, mock_llm_agent)
        result = await handler.apply(sample_job)

        assert result.status == ApplicationStatus.DIRECT_APPLIED
        assert "TestCo" in result.notes

    @pytest.mark.asyncio
    async def test_failed_direct_apply_returns_failed(
        self, mock_page, mock_config, mock_llm_agent, sample_job
    ):
        """Test that a failed direct apply flow returns FAILED status."""
        # Mock LLM agent failure
        mock_llm_agent.navigate_and_apply_direct = AsyncMock(return_value=False)

        # Mock search results
        mock_link = MagicMock()
        mock_link.get_attribute = AsyncMock(return_value="https://testco.com/careers")
        mock_link.inner_text = AsyncMock(return_value="TestCo Careers")
        mock_link.click = AsyncMock()

        mock_results = MagicMock()
        mock_results.count = AsyncMock(return_value=1)
        mock_results.nth = MagicMock(return_value=mock_link)

        mock_page.locator = MagicMock(return_value=mock_results)

        handler = DirectApplyHandler(mock_page, mock_config, mock_llm_agent)
        result = await handler.apply(sample_job)

        assert result.status == ApplicationStatus.FAILED
        assert "did not complete" in result.notes

    @pytest.mark.asyncio
    async def test_no_search_results_returns_failed(
        self, mock_page, mock_config, mock_llm_agent, sample_job
    ):
        """Test that when no search results are found, returns FAILED."""
        # Mock empty search results
        mock_results = MagicMock()
        mock_results.count = AsyncMock(return_value=0)

        mock_page.locator = MagicMock(return_value=mock_results)

        handler = DirectApplyHandler(mock_page, mock_config, mock_llm_agent)
        result = await handler.apply(sample_job)

        assert result.status == ApplicationStatus.FAILED
        assert "career page" in result.notes.lower()

    @pytest.mark.asyncio
    async def test_exception_during_apply_returns_failed(
        self, mock_page, mock_config, mock_llm_agent, sample_job
    ):
        """Test that exceptions during the apply process return FAILED."""
        mock_page.goto = AsyncMock(side_effect=Exception("Navigation timeout"))

        handler = DirectApplyHandler(mock_page, mock_config, mock_llm_agent)
        result = await handler.apply(sample_job)

        assert result.status == ApplicationStatus.FAILED
        assert "Navigation timeout" in result.notes

    @pytest.mark.asyncio
    async def test_calls_llm_agent_methods_in_correct_sequence(
        self, mock_page, mock_config, mock_llm_agent, sample_job
    ):
        """Test that the handler calls LLM agent methods in the correct order."""
        # Mock search results
        mock_link = MagicMock()
        mock_link.get_attribute = AsyncMock(return_value="https://testco.com/careers")
        mock_link.inner_text = AsyncMock(return_value="TestCo Careers Page")
        mock_link.click = AsyncMock()

        mock_results = MagicMock()
        mock_results.count = AsyncMock(return_value=1)
        mock_results.nth = MagicMock(return_value=mock_link)

        mock_page.locator = MagicMock(return_value=mock_results)

        handler = DirectApplyHandler(mock_page, mock_config, mock_llm_agent)
        await handler.apply(sample_job)

        # Verify LLM agent methods were called
        mock_llm_agent.find_company_career_page.assert_called_once_with(
            "TestCo", "Software Engineer", "Bangalore"
        )
        mock_llm_agent.navigate_and_apply_direct.assert_called_once_with(
            mock_page, "TestCo", "Software Engineer", mock_config.user_profile
        )
