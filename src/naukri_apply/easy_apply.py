"""Easy Apply handler for Naukri.com jobs."""

from playwright.async_api import Page

from naukri_apply.config import AppConfig
from naukri_apply.models import ApplicationResult, ApplicationStatus, JobListing


class EasyApplyHandler:
    """Handles the Easy Apply flow on Naukri.com."""

    def __init__(self, page: Page, config: AppConfig):
        self._page = page
        self._config = config

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
            except Exception:
                continue
        return None

    async def _handle_screening_questions(self) -> None:
        """Attempt to handle simple screening questions in modals/chatbot."""
        try:
            # Check for radio button questions - select first option
            radio_buttons = self._page.locator(
                "input[type='radio']"
            )
            count = await radio_buttons.count()
            if count > 0:
                await radio_buttons.first.check()

            # Check for simple select dropdowns - select first non-empty option
            selects = self._page.locator("select")
            select_count = await selects.count()
            for i in range(select_count):
                select_el = selects.nth(i)
                try:
                    options = select_el.locator("option")
                    option_count = await options.count()
                    if option_count > 1:
                        value = await options.nth(1).get_attribute("value")
                        if value:
                            await select_el.select_option(value=value)
                except Exception:
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
                except Exception:
                    continue
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
                except Exception:
                    continue

            # Final timeout-based check
            await self._page.wait_for_timeout(5000)

            # Re-check after waiting
            for indicator in success_indicators:
                try:
                    locator = self._page.locator(indicator).first
                    if await locator.is_visible(timeout=2000):
                        return True
                except Exception:
                    continue

            return False
        except Exception:
            return False
