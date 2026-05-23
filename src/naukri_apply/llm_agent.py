"""LLM Agent module powered by Groq API for intelligent form filling."""

import asyncio
import json
import logging
from typing import Any

from groq import Groq
from playwright.async_api import Page

from naukri_apply.config import AppConfig
from naukri_apply.models import UserProfile

logger = logging.getLogger(__name__)


class LLMAgent:
    """LLM-powered agent for intelligent page analysis and form filling."""

    def __init__(self, config: AppConfig):
        self._config = config
        self._client = Groq(api_key=config.groq_api_key)
        self._model = config.llm.model
        self._max_tokens = config.llm.max_tokens
        self._temperature = config.llm.temperature

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Make a synchronous call to the Groq LLM API."""
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        return response.choices[0].message.content

    async def _call_llm_async(self, system_prompt: str, user_prompt: str) -> str:
        """Wrap the synchronous Groq call in an executor for async usage."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._call_llm, system_prompt, user_prompt
        )

    async def _extract_page_content(self, page: Page) -> str:
        """Extract condensed page content including text and form elements."""
        # Get visible text
        inner_text = await page.evaluate("() => document.body.innerText.slice(0, 3000)")

        # Get form elements with their attributes
        form_elements = await page.evaluate("""() => {
            const elements = document.querySelectorAll(
                'input, select, textarea, button[type="submit"]'
            );
            return Array.from(elements).slice(0, 50).map(el => ({
                tag: el.tagName.toLowerCase(),
                type: el.type || '',
                name: el.name || '',
                id: el.id || '',
                placeholder: el.placeholder || '',
                label: el.labels && el.labels[0] ? el.labels[0].textContent.trim() : '',
                value: el.value || '',
                options: el.tagName === 'SELECT'
                    ? Array.from(el.options).map(o => o.textContent.trim())
                    : []
            }));
        }""")

        content = f"PAGE TEXT:\n{inner_text}\n\nFORM ELEMENTS:\n"
        for el in form_elements:
            content += json.dumps(el) + "\n"

        return content

    def _build_profile_context(self, user_profile: UserProfile) -> str:
        """Build a context string from the user profile."""
        parts = [
            f"Name: {user_profile.name}",
            f"Email: {user_profile.email}",
            f"Phone: {user_profile.phone}",
        ]
        if user_profile.linkedin_url:
            parts.append(f"LinkedIn: {user_profile.linkedin_url}")
        if user_profile.experience_years is not None:
            parts.append(f"Experience: {user_profile.experience_years} years")
        if user_profile.current_company:
            parts.append(f"Current Company: {user_profile.current_company}")
        if user_profile.current_designation:
            parts.append(f"Current Role: {user_profile.current_designation}")
        if user_profile.notice_period:
            parts.append(f"Notice Period: {user_profile.notice_period}")
        return "\n".join(parts)

    async def analyze_page_and_fill_form(
        self, page: Page, user_profile: UserProfile, context: str = ""
    ) -> list[dict[str, Any]]:
        """Analyze page content and return structured form-filling actions.

        Returns a list of actions like:
        [
            {"action": "fill", "selector": "#email", "value": "user@example.com"},
            {"action": "click", "selector": "button[type='submit']"},
            {"action": "select", "selector": "#experience", "value": "5"}
        ]
        """
        try:
            page_content = await self._extract_page_content(page)
            profile_context = self._build_profile_context(user_profile)

            system_prompt = (
                "You are a form-filling assistant. Analyze the page content and form elements, "
                "then return a JSON array of actions to fill the form using the user's profile. "
                "Each action should be one of:\n"
                '- {"action": "fill", "selector": "<css selector>", "value": "<text value>"}\n'
                '- {"action": "click", "selector": "<css selector>"}\n'
                '- {"action": "select", "selector": "<css selector>", "value": "<option value>"}\n'
                "Use the most specific CSS selector available (prefer #id, then [name=...], then other attributes). "
                "Only return the JSON array, no other text."
            )

            user_prompt = (
                f"USER PROFILE:\n{profile_context}\n\n"
                f"ADDITIONAL CONTEXT:\n{context}\n\n"
                f"PAGE CONTENT:\n{page_content}"
            )

            response = await self._call_llm_async(system_prompt, user_prompt)

            # Parse JSON response
            actions = json.loads(response.strip())
            if isinstance(actions, list):
                return actions
            return []

        except (json.JSONDecodeError, Exception) as e:
            logger.debug("LLM analyze_page_and_fill_form failed: %s", e)
            return []

    async def answer_screening_question(
        self, question_text: str, options: list[str], user_profile: UserProfile
    ) -> str:
        """Use the LLM to choose the best answer for a screening question.

        Returns the best option text from the provided options list.
        """
        try:
            profile_context = self._build_profile_context(user_profile)

            system_prompt = (
                "You are helping a job applicant answer screening questions. "
                "Given the question, available options, and the applicant's profile, "
                "select the BEST option that makes the applicant look qualified. "
                "Return ONLY the exact text of the chosen option, nothing else."
            )

            user_prompt = (
                f"APPLICANT PROFILE:\n{profile_context}\n\n"
                f"QUESTION: {question_text}\n\n"
                f"OPTIONS:\n" + "\n".join(f"- {opt}" for opt in options)
            )

            response = await self._call_llm_async(system_prompt, user_prompt)
            answer = response.strip()

            # Try to match response to one of the options
            for opt in options:
                if opt.strip().lower() == answer.lower():
                    return opt

            # Partial match fallback
            for opt in options:
                if opt.strip().lower() in answer.lower() or answer.lower() in opt.strip().lower():
                    return opt

            # If no match, return first option as fallback
            return options[0] if options else ""

        except Exception as e:
            logger.debug("LLM answer_screening_question failed: %s", e)
            return options[0] if options else ""

    async def find_company_career_page(
        self, company_name: str, job_title: str, location: str
    ) -> str:
        """Construct a search query to find the company's career page.

        Returns a search query string for Google.
        """
        try:
            system_prompt = (
                "You are helping find a company's careers page for a specific job. "
                "Given the company name, job title, and location, construct an effective "
                "Google search query to find the direct application page. "
                "Return ONLY the search query string, nothing else."
            )

            user_prompt = (
                f"Company: {company_name}\n"
                f"Job Title: {job_title}\n"
                f"Location: {location}"
            )

            response = await self._call_llm_async(system_prompt, user_prompt)
            return response.strip()

        except Exception as e:
            logger.debug("LLM find_company_career_page failed: %s", e)
            return f"{company_name} {job_title} careers apply"

    async def navigate_and_apply_direct(
        self, page: Page, company_name: str, job_title: str, user_profile: UserProfile
    ) -> bool:
        """Drive the entire flow of finding a job on a company site and applying.

        Returns True if application was submitted successfully, False otherwise.
        """
        try:
            # Get page content after navigation
            page_content = await self._extract_page_content(page)
            profile_context = self._build_profile_context(user_profile)

            system_prompt = (
                "You are navigating a company careers page to apply for a job. "
                "Analyze the page content and determine the next action to take. "
                "If you see an application form, return fill actions. "
                "If you see job listings, return a click action to navigate to the right job. "
                "If you see a submit/apply button and the form is filled, return a click action for it. "
                "Return a JSON array of actions:\n"
                '- {"action": "fill", "selector": "<css selector>", "value": "<text value>"}\n'
                '- {"action": "click", "selector": "<css selector>"}\n'
                '- {"action": "select", "selector": "<css selector>", "value": "<option value>"}\n'
                '- {"action": "done", "success": true/false}\n'
                "Only return the JSON array, no other text."
            )

            user_prompt = (
                f"TARGET JOB:\nCompany: {company_name}\nTitle: {job_title}\n\n"
                f"USER PROFILE:\n{profile_context}\n\n"
                f"PAGE CONTENT:\n{page_content}"
            )

            response = await self._call_llm_async(system_prompt, user_prompt)
            actions = json.loads(response.strip())

            if not isinstance(actions, list):
                return False

            for action in actions:
                action_type = action.get("action")
                if action_type == "done":
                    return action.get("success", False)
                elif action_type == "fill":
                    selector = action.get("selector", "")
                    value = action.get("value", "")
                    if selector and value:
                        await page.fill(selector, value)
                elif action_type == "click":
                    selector = action.get("selector", "")
                    if selector:
                        await page.click(selector)
                        await page.wait_for_load_state("domcontentloaded", timeout=10000)
                elif action_type == "select":
                    selector = action.get("selector", "")
                    value = action.get("value", "")
                    if selector and value:
                        await page.select_option(selector, value=value)

            return True

        except (json.JSONDecodeError, Exception) as e:
            logger.debug("LLM navigate_and_apply_direct failed: %s", e)
            return False
