"""Direct company application handler for quota bypass."""

import logging
from urllib.parse import quote_plus

from playwright.async_api import Page

from naukri_apply.config import AppConfig
from naukri_apply.llm_agent import LLMAgent
from naukri_apply.models import ApplicationResult, ApplicationStatus, JobListing

logger = logging.getLogger(__name__)


class DirectApplyHandler:
    """Handles direct applications on company career sites when Naukri quota is reached."""

    def __init__(self, page: Page, config: AppConfig, llm_agent: LLMAgent):
        self._page = page
        self._config = config
        self._llm_agent = llm_agent

    async def apply(self, job: JobListing) -> ApplicationResult:
        """Search for the job on the company's career site and apply directly.

        Uses the LLM agent to generate an effective search query, navigates
        to the career page via Google, and uses the LLM agent to fill and
        submit the application form.

        Returns ApplicationResult with DIRECT_APPLIED on success or FAILED on error.
        """
        try:
            # Use LLM to generate an effective search query
            career_query = await self._llm_agent.find_company_career_page(
                job.company_name, job.job_title, job.location
            )
            logger.debug("LLM career search query: %s", career_query)

            # Build search URL using the LLM-generated query
            encoded_query = quote_plus(career_query)
            search_url = f"https://www.google.com/search?q={encoded_query}"

            # Navigate to Google search
            await self._page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await self._page.wait_for_timeout(2000)

            # Click the first relevant search result
            clicked = await self._click_search_result(job.company_name)
            if not clicked:
                return ApplicationResult(
                    job=job,
                    status=ApplicationStatus.FAILED,
                    notes="Could not find company career page in search results",
                )

            # Wait for the career page to load
            await self._page.wait_for_load_state("domcontentloaded", timeout=30000)
            await self._page.wait_for_timeout(2000)

            # Use LLM to navigate and apply on the company site
            success = await self._llm_agent.navigate_and_apply_direct(
                self._page,
                job.company_name,
                job.job_title,
                self._config.user_profile,
            )

            if success:
                return ApplicationResult(
                    job=job,
                    status=ApplicationStatus.DIRECT_APPLIED,
                    notes=f"Applied directly on {job.company_name} career site",
                )

            return ApplicationResult(
                job=job,
                status=ApplicationStatus.FAILED,
                notes="Direct application flow did not complete successfully",
            )

        except Exception as e:
            logger.debug("Direct apply failed for %s: %s", job.company_name, e)
            return ApplicationResult(
                job=job,
                status=ApplicationStatus.FAILED,
                notes=f"Direct apply error: {str(e)}",
            )

    async def _click_search_result(self, company_name: str) -> bool:
        """Click the first relevant search result link."""
        try:
            # Look for search result links
            results = self._page.locator("div#search a[href]")
            count = await results.count()

            for i in range(min(count, 10)):
                link = results.nth(i)
                href = await link.get_attribute("href")
                text = await link.inner_text()

                if href and not href.startswith("/search"):
                    # Prefer links that mention the company or careers
                    text_lower = text.lower()
                    company_lower = company_name.lower()
                    if company_lower in text_lower or "career" in text_lower:
                        await link.click()
                        return True

            # Fallback: click first non-google link
            for i in range(min(count, 5)):
                link = results.nth(i)
                href = await link.get_attribute("href")
                if href and "google" not in href:
                    await link.click()
                    return True

            return False

        except Exception as e:
            logger.debug("Error clicking search result: %s", e)
            return False
