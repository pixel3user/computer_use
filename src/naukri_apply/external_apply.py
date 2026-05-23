"""External site application handler."""

import logging
from typing import TYPE_CHECKING

from playwright.async_api import BrowserContext, Page

from naukri_apply.config import AppConfig
from naukri_apply.form_filler import (
    fill_text_field,
    find_field,
    upload_file,
)
from naukri_apply.models import ApplicationResult, ApplicationStatus, JobListing

if TYPE_CHECKING:
    from naukri_apply.llm_agent import LLMAgent

logger = logging.getLogger(__name__)


class ExternalApplyHandler:
    """Handles applications that redirect to external ATS platforms."""

    def __init__(self, page: Page, config: AppConfig, llm_agent: "LLMAgent | None" = None):
        self._page = page
        self._config = config
        self._llm_agent = llm_agent

    async def apply(self, job: JobListing) -> ApplicationResult:
        """Click Apply, detect new tab, fill form on external site.

        Returns ApplicationResult with EXTERNAL_PARTIAL status on partial success,
        or FAILED on error.
        """
        try:
            # Find and click the Apply button, listening for new tab
            context: BrowserContext = self._page.context
            new_page = await self._click_apply_and_get_new_page(context)

            if new_page is None:
                # No new tab opened, might have redirected in same page
                new_page = self._page

            # Wait for the external page to load
            await new_page.wait_for_load_state("domcontentloaded", timeout=30000)

            # Detect platform
            platform = self._detect_platform(new_page.url)

            # Check if it's a signup/registration form
            is_signup = await self._is_signup_form(new_page)

            if is_signup:
                await self._fill_signup_form(new_page)
            else:
                await self._fill_application_form(new_page)

            # Attempt to submit
            await self._submit_form(new_page)

            # Close the external tab if it's not the main page
            if new_page != self._page:
                await new_page.close()

            return ApplicationResult(
                job=job,
                status=ApplicationStatus.EXTERNAL_PARTIAL,
                notes=f"External application attempted on {platform or 'unknown'} platform",
            )

        except Exception as e:
            logger.debug("External apply failed: %s", e)
            return ApplicationResult(
                job=job,
                status=ApplicationStatus.FAILED,
                notes=f"External apply error: {str(e)}",
            )

    async def _click_apply_and_get_new_page(self, context: BrowserContext) -> Page | None:
        """Click the apply button and detect if a new tab opens."""
        apply_selectors = [
            "button:has-text('Apply')",
            "a:has-text('Apply')",
            "button:has-text('Apply Now')",
            "a:has-text('Apply Now')",
            "[class*='apply-button']",
        ]

        for selector in apply_selectors:
            try:
                locator = self._page.locator(selector).first
                if await locator.is_visible(timeout=3000):
                    # Listen for new page event
                    async with context.expect_page(timeout=10000) as new_page_info:
                        await locator.click()
                    new_page = await new_page_info.value
                    return new_page
            except Exception as e:
                logger.debug("Selector '%s' did not open new page: %s", selector, e)
                continue

        # Fallback: try clicking without expecting new page
        for selector in apply_selectors:
            try:
                locator = self._page.locator(selector).first
                if await locator.is_visible(timeout=3000):
                    await locator.click()
                    await self._page.wait_for_timeout(3000)
                    return None
            except Exception as e:
                logger.debug("Fallback click failed for '%s': %s", selector, e)
                continue

        return None

    def _detect_platform(self, url: str) -> str | None:
        """Detect the ATS platform from the URL."""
        platform_patterns = {
            "greenhouse": "greenhouse.io",
            "lever": "lever.co",
            "workday": "workday.com",
            "icims": "icims.com",
            "taleo": "taleo.net",
            "successfactors": "successfactors.com",
            "smartrecruiters": "smartrecruiters.com",
            "bamboohr": "bamboohr.com",
            "ashbyhq": "ashbyhq.com",
            "recruitee": "recruitee.com",
        }
        url_lower = url.lower()
        for platform, domain in platform_patterns.items():
            if domain in url_lower:
                return platform
        return None

    async def _is_signup_form(self, page: Page) -> bool:
        """Check if the page contains a signup/registration form."""
        signup_indicators = [
            "text=Sign Up",
            "text=Create Account",
            "text=Register",
            "text=sign up",
            "text=create account",
            "text=register",
        ]
        for indicator in signup_indicators:
            try:
                locator = page.locator(indicator).first
                if await locator.is_visible(timeout=3000):
                    return True
            except Exception as e:
                logger.debug("Signup indicator '%s' check failed: %s", indicator, e)
                continue
        return False

    async def _fill_signup_form(self, page: Page) -> None:
        """Fill signup/registration form with email and password."""
        profile = self._config.user_profile

        email_field = await find_field(page, "email")
        if email_field:
            await fill_text_field(email_field, profile.email)

        password_field = await find_field(page, "password")
        if password_field:
            if self._config.signup_password:
                await fill_text_field(password_field, self._config.signup_password)
            else:
                logger.debug("No signup_password configured; skipping password field")

        # Use LLM for any additional signup fields
        if self._llm_agent:
            try:
                actions = await self._llm_agent.analyze_page_and_fill_form(
                    page, profile, context="Signup/registration form"
                )
                for action in actions:
                    action_type = action.get("action")
                    selector = action.get("selector", "")
                    value = action.get("value", "")
                    try:
                        if action_type == "fill" and selector and value:
                            await page.fill(selector, value)
                        elif action_type == "select" and selector and value:
                            await page.select_option(selector, value=value)
                        elif action_type == "click" and selector:
                            await page.click(selector)
                    except Exception as e:
                        logger.debug("LLM signup action failed (%s): %s", action, e)
            except Exception as e:
                logger.debug("LLM signup form analysis failed: %s", e)

    async def _fill_application_form(self, page: Page) -> None:
        """Fill application form fields from user profile."""
        profile = self._config.user_profile

        # Fill name
        name_field = await find_field(page, "name")
        if name_field:
            await fill_text_field(name_field, profile.name)

        # Fill email
        email_field = await find_field(page, "email")
        if email_field:
            await fill_text_field(email_field, profile.email)

        # Fill phone
        phone_field = await find_field(page, "phone")
        if phone_field:
            await fill_text_field(phone_field, profile.phone)

        # Fill LinkedIn URL
        if profile.linkedin_url:
            linkedin_field = await find_field(page, "linkedin")
            if linkedin_field:
                await fill_text_field(linkedin_field, profile.linkedin_url)

        # Fill experience
        if profile.experience_years is not None:
            exp_field = await find_field(page, "experience")
            if exp_field:
                await fill_text_field(exp_field, str(profile.experience_years))

        # Fill current company
        if profile.current_company:
            company_field = await find_field(page, "company")
            if company_field:
                await fill_text_field(company_field, profile.current_company)

        # Upload resume
        resume_field = await find_field(page, "resume")
        if resume_field:
            await upload_file(page, resume_field, str(profile.resume_path))

        # Use LLM for any remaining unfilled fields
        if self._llm_agent:
            try:
                actions = await self._llm_agent.analyze_page_and_fill_form(
                    page, profile, context="External application form"
                )
                for action in actions:
                    action_type = action.get("action")
                    selector = action.get("selector", "")
                    value = action.get("value", "")
                    try:
                        if action_type == "fill" and selector and value:
                            await page.fill(selector, value)
                        elif action_type == "select" and selector and value:
                            await page.select_option(selector, value=value)
                        elif action_type == "click" and selector:
                            await page.click(selector)
                    except Exception as e:
                        logger.debug("LLM action failed (%s): %s", action, e)
            except Exception as e:
                logger.debug("LLM form analysis failed: %s", e)

    async def _submit_form(self, page: Page) -> None:
        """Try to submit the form."""
        submit_selectors = [
            "button[type='submit']",
            "button:has-text('Submit')",
            "button:has-text('Apply')",
            "button:has-text('Submit Application')",
            "input[type='submit']",
        ]
        for selector in submit_selectors:
            try:
                locator = page.locator(selector).first
                if await locator.is_visible(timeout=3000):
                    await locator.click()
                    await page.wait_for_timeout(3000)
                    return
            except Exception as e:
                logger.debug("Submit selector '%s' failed: %s", selector, e)
                continue
