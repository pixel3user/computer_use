"""Easy Apply handler for Naukri.com jobs."""

import logging
from typing import TYPE_CHECKING

from playwright.async_api import Page

from naukri_apply.config import AppConfig
from naukri_apply.models import ApplicationResult, ApplicationStatus, JobListing

if TYPE_CHECKING:
    from naukri_apply.llm_agent import LLMAgent

logger = logging.getLogger(__name__)


class EasyApplyHandler:
    """Handles the Easy Apply flow on Naukri.com."""

    def __init__(self, page: Page, config: AppConfig, llm_agent: "LLMAgent | None" = None):
        self._page = page
        self._config = config
        self._llm_agent = llm_agent

    async def apply(self, job: JobListing) -> ApplicationResult:
        """Click Apply, handle dialogs/questionnaires, and confirm application.

        Returns an ApplicationResult with APPLIED status on success,
        or FAILED status with error details.
        """
        try:
            # Find and click the Apply button
            apply_button = await self._find_apply_button()
            if apply_button is None:
                return ApplicationResult(
                    job=job,
                    status=ApplicationStatus.FAILED,
                    notes="Apply button not found",
                )

            await apply_button.click()

            # Wait for any modal/dialog that appears
            await self._page.wait_for_timeout(2000)

            # Handle chatbot/screening questions if they appear
            await self._handle_screening_questions()

            # Wait for success confirmation
            success = await self._wait_for_success()
            if success:
                return ApplicationResult(
                    job=job,
                    status=ApplicationStatus.APPLIED,
                    notes="Applied successfully via Easy Apply",
                )

            return ApplicationResult(
                job=job,
                status=ApplicationStatus.FAILED,
                notes="Could not confirm successful application",
            )

        except Exception as e:
            return ApplicationResult(
                job=job,
                status=ApplicationStatus.FAILED,
                notes=f"Easy Apply error: {str(e)}",
            )

    async def _find_apply_button(self):
        """Locate the Apply/Easy Apply button on the page."""
        selectors = [
            "button:has-text('Apply')",
            "button:has-text('Easy Apply')",
            "button:has-text('Apply Now')",
            "a:has-text('Apply')",
            "#apply-button",
            "[class*='apply-button']",
        ]
        for selector in selectors:
            try:
                locator = self._page.locator(selector).first
                if await locator.is_visible(timeout=3000):
                    return locator
            except Exception as e:
                logger.debug("Apply button selector '%s' failed: %s", selector, e)
                continue
        return None

    async def _handle_screening_questions(self) -> None:
        """Attempt to handle simple screening questions in modals/chatbot."""
        try:
            # Check for radio button questions
            radio_buttons = self._page.locator(
                "input[type='radio']"
            )
            count = await radio_buttons.count()
            if count > 0:
                if self._llm_agent:
                    # Use LLM to pick the best radio option
                    await self._handle_radio_with_llm(radio_buttons, count)
                else:
                    # Fallback: select first option
                    await radio_buttons.first.check()

            # Check for simple select dropdowns
            selects = self._page.locator("select")
            select_count = await selects.count()
            for i in range(select_count):
                select_el = selects.nth(i)
                try:
                    options = select_el.locator("option")
                    option_count = await options.count()
                    if option_count > 1:
                        if self._llm_agent:
                            await self._handle_select_with_llm(select_el, options, option_count)
                        else:
                            value = await options.nth(1).get_attribute("value")
                            if value:
                                await select_el.select_option(value=value)
                except Exception as e:
                    logger.debug("Failed to handle select dropdown %d: %s", i, e)
                    continue

            # Look for submit/next/continue button in the modal
            submit_selectors = [
                "button:has-text('Submit')",
                "button:has-text('Next')",
                "button:has-text('Continue')",
                "button:has-text('Apply')",
            ]
            for selector in submit_selectors:
                try:
                    btn = self._page.locator(selector).first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        await self._page.wait_for_timeout(1000)
                        break
                except Exception as e:
                    logger.debug("Screening submit selector '%s' failed: %s", selector, e)
                    continue
        except Exception as e:
            logger.debug("Error handling screening questions: %s", e)

    async def _handle_radio_with_llm(self, radio_buttons, count: int) -> None:
        """Use LLM to select the best radio button option."""
        try:
            # Extract question text and options
            question_text = ""
            option_texts = []

            # Try to get the question text from nearby label or heading
            parent = self._page.locator("input[type='radio']").first.locator("..")
            question_text = await parent.inner_text()

            for i in range(count):
                radio = radio_buttons.nth(i)
                label = await radio.evaluate(
                    "el => el.labels && el.labels[0] ? el.labels[0].textContent.trim() : el.value"
                )
                option_texts.append(label)

            if option_texts:
                best_answer = await self._llm_agent.answer_screening_question(
                    question_text, option_texts, self._config.user_profile
                )
                # Find and check the matching radio button
                for i, opt in enumerate(option_texts):
                    if opt == best_answer:
                        await radio_buttons.nth(i).check()
                        return

            # Fallback to first option
            await radio_buttons.first.check()
        except Exception as e:
            logger.debug("LLM radio handling failed, using fallback: %s", e)
            await radio_buttons.first.check()

    async def _handle_select_with_llm(self, select_el, options, option_count: int) -> None:
        """Use LLM to select the best dropdown option."""
        try:
            option_texts = []
            for i in range(option_count):
                text = await options.nth(i).inner_text()
                if text.strip():
                    option_texts.append(text.strip())

            if len(option_texts) > 1:
                # Get question context from label if available
                label_text = await select_el.evaluate(
                    "el => el.labels && el.labels[0] ? el.labels[0].textContent.trim() : ''"
                )
                best_answer = await self._llm_agent.answer_screening_question(
                    label_text or "Select the best option",
                    option_texts,
                    self._config.user_profile,
                )
                # Select by visible text matching
                for i in range(option_count):
                    text = await options.nth(i).inner_text()
                    if text.strip() == best_answer:
                        value = await options.nth(i).get_attribute("value")
                        if value:
                            await select_el.select_option(value=value)
                            return

            # Fallback to second option (skip empty first)
            value = await options.nth(1).get_attribute("value")
            if value:
                await select_el.select_option(value=value)
        except Exception as e:
            logger.debug("LLM select handling failed, using fallback: %s", e)
            try:
                value = await options.nth(1).get_attribute("value")
                if value:
                    await select_el.select_option(value=value)
            except Exception:
                pass

    async def _wait_for_success(self) -> bool:
        """Wait for success indicators after applying."""
        success_indicators = [
            "text=applied successfully",
            "text=Applied",
            "text=Application Submitted",
            "text=Already Applied",
            "[class*='applied']",
            "[class*='success']",
        ]
        try:
            for indicator in success_indicators:
                try:
                    locator = self._page.locator(indicator).first
                    if await locator.is_visible(timeout=5000):
                        return True
                except Exception as e:
                    logger.debug("Success indicator '%s' check failed: %s", indicator, e)
                    continue

            # Final timeout-based check
            await self._page.wait_for_timeout(5000)

            # Re-check after waiting
            for indicator in success_indicators:
                try:
                    locator = self._page.locator(indicator).first
                    if await locator.is_visible(timeout=2000):
                        return True
                except Exception as e:
                    logger.debug("Re-check indicator '%s' failed: %s", indicator, e)
                    continue

            return False
        except Exception as e:
            logger.debug("Error waiting for success confirmation: %s", e)
            return False
