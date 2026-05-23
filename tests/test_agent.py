"""Tests for the NaukriAgent class."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from naukri_apply.agent import NaukriAgent
from naukri_apply.models import ApplicationStatus, ApplyType


class TestNaukriAgentInit:
    def test_raises_value_error_when_groq_api_key_is_none(self, mock_app_config):
        mock_app_config.groq_api_key = None
        browser = MagicMock()

        with pytest.raises(ValueError, match="GROQ_API_KEY is required"):
            NaukriAgent(config=mock_app_config, browser=browser)

    def test_raises_value_error_when_groq_api_key_is_empty(self, mock_app_config):
        mock_app_config.groq_api_key = ""
        browser = MagicMock()

        with pytest.raises(ValueError, match="GROQ_API_KEY is required"):
            NaukriAgent(config=mock_app_config, browser=browser)

    def test_initializes_successfully_with_valid_key(self, mock_app_config):
        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)
        assert agent._max_steps == 50
        assert agent._max_steps_dry_run == 10


class TestBuildProfileContext:
    def test_build_profile_context_includes_all_fields(self, mock_app_config):
        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)
        profile = mock_app_config.user_profile

        context = agent._build_profile_context(profile)

        assert "Name: Test User" in context
        assert "Email: test@example.com" in context
        assert "Phone: +91-9876543210" in context
        assert "LinkedIn: https://linkedin.com/in/testuser" in context
        assert "Experience: 5 years" in context
        assert "Current Company: Test Corp" in context
        assert "Current Role: Software Engineer" in context
        assert "Notice Period: 30 days" in context
        assert "resume.pdf" in context

    def test_build_profile_context_minimal_profile(self, mock_app_config):
        from pathlib import Path

        from naukri_apply.models import UserProfile

        minimal_profile = UserProfile(
            name="Min User",
            email="min@example.com",
            phone="1234567890",
            resume_path=Path("resume.pdf"),
        )

        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)
        context = agent._build_profile_context(minimal_profile)

        assert "Name: Min User" in context
        assert "Email: min@example.com" in context
        assert "Phone: 1234567890" in context
        # Optional fields should not appear
        assert "LinkedIn:" not in context
        assert "Experience:" not in context
        assert "Current Company:" not in context
        assert "Current Role:" not in context
        assert "Notice Period:" not in context


class TestApplyToJob:
    @pytest.mark.asyncio
    @patch("naukri_apply.agent.Agent")
    async def test_apply_to_job_constructs_agent_with_correct_params(
        self, MockAgent, mock_app_config
    ):
        mock_history = MagicMock()
        mock_history.final_result.return_value = (
            "JOB_TITLE: Dev\n"
            "COMPANY: Corp\n"
            "LOCATION: Delhi\n"
            "APPLY_TYPE: easy_apply\n"
            "STATUS: applied\n"
            "NOTES: Success"
        )
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_history)
        MockAgent.return_value = mock_agent_instance

        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)
        url = "https://www.naukri.com/job-12345"

        await agent.apply_to_job(url)

        MockAgent.assert_called_once()
        call_kwargs = MockAgent.call_args[1]
        assert url in call_kwargs["task"]
        assert call_kwargs["browser"] is browser
        assert call_kwargs["llm"] is agent._llm

    @pytest.mark.asyncio
    @patch("naukri_apply.agent.Agent")
    async def test_apply_to_job_returns_applied_on_success(
        self, MockAgent, mock_app_config
    ):
        mock_history = MagicMock()
        mock_history.final_result.return_value = (
            "JOB_TITLE: Dev\n"
            "COMPANY: Corp\n"
            "LOCATION: Delhi\n"
            "APPLY_TYPE: easy_apply\n"
            "STATUS: applied\n"
            "NOTES: Success"
        )
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_history)
        MockAgent.return_value = mock_agent_instance

        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        result = await agent.apply_to_job("https://www.naukri.com/job-12345")

        assert result.status == ApplicationStatus.APPLIED
        assert result.job.job_title == "Dev"
        assert result.job.company_name == "Corp"
        assert result.job.location == "Delhi"
        assert result.job.apply_type == ApplyType.EASY_APPLY
        assert result.notes == "Success"

    @pytest.mark.asyncio
    @patch("naukri_apply.agent.Agent")
    async def test_apply_to_job_returns_failed_on_agent_exception(
        self, MockAgent, mock_app_config
    ):
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(side_effect=Exception("Connection timeout"))
        MockAgent.return_value = mock_agent_instance

        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        result = await agent.apply_to_job("https://www.naukri.com/job-12345")

        assert result.status == ApplicationStatus.FAILED
        assert "Connection timeout" in result.notes

    @pytest.mark.asyncio
    @patch("naukri_apply.agent.Agent")
    async def test_apply_to_job_dry_run_returns_skipped(
        self, MockAgent, mock_app_config
    ):
        mock_history = MagicMock()
        mock_history.final_result.return_value = (
            "JOB_TITLE: Dev\n"
            "COMPANY: Corp\n"
            "LOCATION: Delhi\n"
            "APPLY_TYPE: easy_apply\n"
        )
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_history)
        MockAgent.return_value = mock_agent_instance

        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        result = await agent.apply_to_job(
            "https://www.naukri.com/job-12345", dry_run=True
        )

        assert result.status == ApplicationStatus.SKIPPED
        assert "Dry run" in result.notes
        # Verify dry run uses reduced max_steps
        mock_agent_instance.run.assert_called_once_with(max_steps=10)

    @pytest.mark.asyncio
    @patch("naukri_apply.agent.Agent")
    async def test_apply_to_job_passes_available_file_paths(
        self, MockAgent, mock_app_config
    ):
        mock_history = MagicMock()
        mock_history.final_result.return_value = (
            "JOB_TITLE: Dev\n"
            "COMPANY: Corp\n"
            "LOCATION: Delhi\n"
            "APPLY_TYPE: easy_apply\n"
            "STATUS: applied\n"
            "NOTES: Success"
        )
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_history)
        MockAgent.return_value = mock_agent_instance

        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        await agent.apply_to_job("https://www.naukri.com/job-12345")

        call_kwargs = MockAgent.call_args[1]
        assert "available_file_paths" in call_kwargs
        assert "resume.pdf" in call_kwargs["available_file_paths"][0]


class TestDirectApply:
    @pytest.mark.asyncio
    @patch("naukri_apply.agent.Agent")
    async def test_direct_apply_returns_direct_applied_on_success(
        self, MockAgent, mock_app_config, sample_job_listing
    ):
        mock_history = MagicMock()
        mock_history.final_result.return_value = (
            "STATUS: applied\n" "NOTES: Applied via company career page"
        )
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_history)
        MockAgent.return_value = mock_agent_instance

        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        result = await agent.direct_apply(sample_job_listing)

        assert result.status == ApplicationStatus.DIRECT_APPLIED
        assert "Applied via company career page" in result.notes

    @pytest.mark.asyncio
    @patch("naukri_apply.agent.Agent")
    async def test_direct_apply_returns_failed_on_error(
        self, MockAgent, mock_app_config, sample_job_listing
    ):
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(side_effect=Exception("Network error"))
        MockAgent.return_value = mock_agent_instance

        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        result = await agent.direct_apply(sample_job_listing)

        assert result.status == ApplicationStatus.FAILED
        assert "Network error" in result.notes


class TestCheckLoginStatus:
    @pytest.mark.asyncio
    @patch("naukri_apply.agent.Agent")
    async def test_check_login_status_returns_true(self, MockAgent, mock_app_config):
        mock_history = MagicMock()
        mock_history.final_result.return_value = "LOGGED_IN"
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_history)
        MockAgent.return_value = mock_agent_instance

        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        result = await agent.check_login_status()

        assert result is True

    @pytest.mark.asyncio
    @patch("naukri_apply.agent.Agent")
    async def test_check_login_status_returns_false(self, MockAgent, mock_app_config):
        mock_history = MagicMock()
        mock_history.final_result.return_value = "NOT_LOGGED_IN"
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_history)
        MockAgent.return_value = mock_agent_instance

        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        result = await agent.check_login_status()

        assert result is False

    @pytest.mark.asyncio
    @patch("naukri_apply.agent.Agent")
    async def test_check_login_status_returns_false_on_error(
        self, MockAgent, mock_app_config
    ):
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(side_effect=Exception("Timeout"))
        MockAgent.return_value = mock_agent_instance

        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        result = await agent.check_login_status()

        assert result is False


class TestParseResult:
    def test_parse_result_extracts_fields(self, mock_app_config):
        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        text = (
            "JOB_TITLE: Software Engineer\n"
            "COMPANY: Google\n"
            "LOCATION: Bangalore\n"
            "APPLY_TYPE: easy_apply\n"
            "STATUS: applied\n"
            "NOTES: Done"
        )
        url = "https://www.naukri.com/job-99"
        job = agent._parse_result(text, url)

        assert job.job_title == "Software Engineer"
        assert job.company_name == "Google"
        assert job.location == "Bangalore"
        assert job.apply_type == ApplyType.EASY_APPLY
        assert job.url == url

    def test_parse_result_handles_missing_fields(self, mock_app_config):
        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        text = ""
        url = "https://www.naukri.com/job-99"
        job = agent._parse_result(text, url)

        assert job.job_title == "Unknown"
        assert job.company_name == "Unknown"
        assert job.location == "Unknown"
        assert job.apply_type == ApplyType.UNKNOWN
        assert job.url == url


class TestDetermineStatus:
    def test_determine_status_applied(self, mock_app_config):
        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        text = "STATUS: applied\nNOTES: done"
        assert agent._determine_status(text) == ApplicationStatus.APPLIED

    def test_determine_status_failed(self, mock_app_config):
        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        text = "STATUS: failed\nNOTES: error occurred"
        assert agent._determine_status(text) == ApplicationStatus.FAILED

    def test_determine_status_external_partial(self, mock_app_config):
        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        text = "STATUS: external_partial\nNOTES: redirected"
        assert agent._determine_status(text) == ApplicationStatus.EXTERNAL_PARTIAL

    def test_determine_status_no_false_positive_when_status_present(self, mock_app_config):
        """STATUS field with unrecognized value should not fall through to heuristic."""
        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        # STATUS field is present but with an unrecognized value.
        # The text also contains 'successfully' which should NOT trigger a false positive.
        text = "STATUS: unknown_value\nNOTES: the form was not successfully submitted"
        assert agent._determine_status(text) == ApplicationStatus.FAILED

    def test_determine_status_fallback_heuristic_when_status_absent(self, mock_app_config):
        """When STATUS field is completely absent, fallback heuristic should work."""
        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        text = "The application was successfully submitted to the company."
        assert agent._determine_status(text) == ApplicationStatus.APPLIED

    def test_determine_status_fallback_returns_failed_when_no_indicators(self, mock_app_config):
        """When STATUS field is absent and no success indicators, return FAILED."""
        browser = MagicMock()
        agent = NaukriAgent(config=mock_app_config, browser=browser)

        text = "Something went wrong during the process."
        assert agent._determine_status(text) == ApplicationStatus.FAILED


class TestExtractField:
    def test_extract_field_finds_value(self):
        text = "JOB_TITLE: Senior Dev\nCOMPANY: Acme"
        assert NaukriAgent._extract_field(text, "JOB_TITLE") == "Senior Dev"
        assert NaukriAgent._extract_field(text, "COMPANY") == "Acme"

    def test_extract_field_returns_empty_when_not_found(self):
        text = "JOB_TITLE: Senior Dev\nCOMPANY: Acme"
        assert NaukriAgent._extract_field(text, "LOCATION") == ""
        assert NaukriAgent._extract_field(text, "NOTES") == ""
