"""Tests for LLMAgent class."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from naukri_apply.models import LLMConfig, QuotaConfig, UserProfile


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.groq_api_key = "test-api-key"
    config.llm = LLMConfig(
        enabled=True,
        model="meta-llama/llama-4-maverick-17b-128e-instruct",
        max_tokens=4096,
        temperature=0.2,
    )
    config.quota = QuotaConfig()
    return config


@pytest.fixture
def mock_user_profile():
    return UserProfile(
        name="Test User",
        email="test@example.com",
        phone="+91-9876543210",
        resume_path="./resume.pdf",
        linkedin_url="https://linkedin.com/in/testuser",
        experience_years=5,
        current_company="TestCorp",
        current_designation="Software Engineer",
        notice_period="30 days",
    )


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.evaluate = AsyncMock()
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.select_option = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    return page


class TestLLMAgent:
    """Tests for LLMAgent with mocked Groq client."""

    @patch("naukri_apply.llm_agent.Groq")
    def test_init_creates_groq_client(self, mock_groq_cls, mock_config):
        from naukri_apply.llm_agent import LLMAgent

        agent = LLMAgent(mock_config)

        mock_groq_cls.assert_called_once_with(api_key="test-api-key")
        assert agent._model == "meta-llama/llama-4-maverick-17b-128e-instruct"
        assert agent._max_tokens == 4096
        assert agent._temperature == 0.2

    @pytest.mark.asyncio
    @patch("naukri_apply.llm_agent.Groq")
    async def test_analyze_page_and_fill_form_returns_actions(
        self, mock_groq_cls, mock_config, mock_page, mock_user_profile
    ):
        from naukri_apply.llm_agent import LLMAgent

        # Setup mock LLM response
        actions_response = json.dumps([
            {"action": "fill", "selector": "#email", "value": "test@example.com"},
            {"action": "click", "selector": "button[type='submit']"},
        ])

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content=actions_response))]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_completion
        mock_groq_cls.return_value = mock_client

        # Mock page content extraction
        mock_page.evaluate = AsyncMock(side_effect=[
            "Page text content here",  # innerText
            [{"tag": "input", "type": "email", "name": "email", "id": "email",
              "placeholder": "Enter email", "label": "Email", "value": "", "options": []}],
        ])

        agent = LLMAgent(mock_config)
        result = await agent.analyze_page_and_fill_form(
            mock_page, mock_user_profile, context="Test"
        )

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["action"] == "fill"
        assert result[0]["selector"] == "#email"
        assert result[1]["action"] == "click"

    @pytest.mark.asyncio
    @patch("naukri_apply.llm_agent.Groq")
    async def test_answer_screening_question_returns_correct_choice(
        self, mock_groq_cls, mock_config, mock_user_profile
    ):
        from naukri_apply.llm_agent import LLMAgent

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content="5+ years"))]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_completion
        mock_groq_cls.return_value = mock_client

        agent = LLMAgent(mock_config)
        result = await agent.answer_screening_question(
            "How many years of experience do you have?",
            ["0-2 years", "3-5 years", "5+ years"],
            mock_user_profile,
        )

        assert result == "5+ years"

    @pytest.mark.asyncio
    @patch("naukri_apply.llm_agent.Groq")
    async def test_answer_screening_question_partial_match(
        self, mock_groq_cls, mock_config, mock_user_profile
    ):
        from naukri_apply.llm_agent import LLMAgent

        # LLM returns slightly different text that partially matches
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content="Yes, I am willing to relocate"))]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_completion
        mock_groq_cls.return_value = mock_client

        agent = LLMAgent(mock_config)
        result = await agent.answer_screening_question(
            "Are you willing to relocate?",
            ["Yes", "No", "Maybe"],
            mock_user_profile,
        )

        assert result == "Yes"

    @pytest.mark.asyncio
    @patch("naukri_apply.llm_agent.Groq")
    async def test_find_company_career_page_returns_query(
        self, mock_groq_cls, mock_config
    ):
        from naukri_apply.llm_agent import LLMAgent

        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Google Software Engineer Bangalore careers apply"))
        ]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_completion
        mock_groq_cls.return_value = mock_client

        agent = LLMAgent(mock_config)
        result = await agent.find_company_career_page("Google", "Software Engineer", "Bangalore")

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Google" in result

    @pytest.mark.asyncio
    @patch("naukri_apply.llm_agent.Groq")
    async def test_analyze_page_handles_api_error_gracefully(
        self, mock_groq_cls, mock_config, mock_page, mock_user_profile
    ):
        from naukri_apply.llm_agent import LLMAgent

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API rate limit")
        mock_groq_cls.return_value = mock_client

        mock_page.evaluate = AsyncMock(side_effect=[
            "Page text",
            [{"tag": "input", "type": "text", "name": "name", "id": "",
              "placeholder": "", "label": "", "value": "", "options": []}],
        ])

        agent = LLMAgent(mock_config)
        result = await agent.analyze_page_and_fill_form(
            mock_page, mock_user_profile, context=""
        )

        # Should return empty list on error, not raise
        assert result == []

    @pytest.mark.asyncio
    @patch("naukri_apply.llm_agent.Groq")
    async def test_answer_screening_question_handles_error_returns_first_option(
        self, mock_groq_cls, mock_config, mock_user_profile
    ):
        from naukri_apply.llm_agent import LLMAgent

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Network error")
        mock_groq_cls.return_value = mock_client

        agent = LLMAgent(mock_config)
        result = await agent.answer_screening_question(
            "Question?",
            ["Option A", "Option B"],
            mock_user_profile,
        )

        # Should fall back to first option
        assert result == "Option A"

    @pytest.mark.asyncio
    @patch("naukri_apply.llm_agent.Groq")
    async def test_find_company_career_page_handles_error(
        self, mock_groq_cls, mock_config
    ):
        from naukri_apply.llm_agent import LLMAgent

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Timeout")
        mock_groq_cls.return_value = mock_client

        agent = LLMAgent(mock_config)
        result = await agent.find_company_career_page("Acme", "Developer", "Delhi")

        # Should return a fallback search query
        assert "Acme" in result
        assert "Developer" in result

    @pytest.mark.asyncio
    @patch("naukri_apply.llm_agent.Groq")
    async def test_navigate_and_apply_direct_success(
        self, mock_groq_cls, mock_config, mock_page, mock_user_profile
    ):
        from naukri_apply.llm_agent import LLMAgent

        actions_response = json.dumps([
            {"action": "fill", "selector": "#name", "value": "Test User"},
            {"action": "click", "selector": "button[type='submit']"},
            {"action": "done", "success": True},
        ])

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content=actions_response))]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_completion
        mock_groq_cls.return_value = mock_client

        mock_page.evaluate = AsyncMock(side_effect=[
            "Career page content",
            [{"tag": "input", "type": "text", "name": "name", "id": "name",
              "placeholder": "", "label": "Name", "value": "", "options": []}],
        ])

        agent = LLMAgent(mock_config)
        result = await agent.navigate_and_apply_direct(
            mock_page, "TestCo", "Engineer", mock_user_profile
        )

        assert result is True

    @pytest.mark.asyncio
    @patch("naukri_apply.llm_agent.Groq")
    async def test_navigate_and_apply_direct_failure(
        self, mock_groq_cls, mock_config, mock_page, mock_user_profile
    ):
        from naukri_apply.llm_agent import LLMAgent

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Error")
        mock_groq_cls.return_value = mock_client

        mock_page.evaluate = AsyncMock(side_effect=[
            "Page text",
            [],
        ])

        agent = LLMAgent(mock_config)
        result = await agent.navigate_and_apply_direct(
            mock_page, "TestCo", "Engineer", mock_user_profile
        )

        assert result is False
