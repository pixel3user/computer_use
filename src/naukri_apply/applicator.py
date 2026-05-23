"""Job page navigation and metadata extraction."""

from playwright.async_api import Page

from naukri_apply.config import AppConfig
from naukri_apply.models import ApplyType, JobListing


class JobApplicator:
    """Navigates to a job listing page and extracts metadata."""

    def __init__(self, page: Page, config: AppConfig):
        self._page = page
        self._config = config

    async def process_job(self, url: str) -> JobListing:
        """Navigate to a job URL and extract listing metadata.

        Returns a JobListing with extracted company name, job title,
        location, and apply type.
        """
        await self._page.goto(url, timeout=30000, wait_until="domcontentloaded")

        job_title = await self._extract_job_title()
        company_name = await self._extract_company_name()
        location = await self._extract_location()
        apply_type = await self._determine_apply_type()

        return JobListing(
            company_name=company_name,
            job_title=job_title,
            location=location,
            url=url,
            apply_type=apply_type,
        )

    async def _extract_job_title(self) -> str:
        """Extract job title from the page."""
        selectors = [
            ".jd-header-title",
            "h1.jd-header-title",
            "[class*='title']",
            "h1",
        ]
        for selector in selectors:
            try:
                element = self._page.locator(selector).first
                if await element.is_visible(timeout=3000):
                    text = await element.text_content()
                    if text and text.strip():
                        return text.strip()
            except Exception:
                continue
        return "Unknown"

    async def _extract_company_name(self) -> str:
        """Extract company name from the page."""
        selectors = [
            ".jd-header-comp-name a",
            ".company-name",
            "[class*='company']",
            "a[href*='/company/']",
        ]
        for selector in selectors:
            try:
                element = self._page.locator(selector).first
                if await element.is_visible(timeout=3000):
                    text = await element.text_content()
                    if text and text.strip():
                        return text.strip()
            except Exception:
                continue
        return "Unknown"

    async def _extract_location(self) -> str:
        """Extract job location from the page."""
        selectors = [
            ".location",
            "[class*='location']",
            ".loc",
            "[class*='loc']",
        ]
        for selector in selectors:
            try:
                element = self._page.locator(selector).first
                if await element.is_visible(timeout=3000):
                    text = await element.text_content()
                    if text and text.strip():
                        return text.strip()
            except Exception:
                continue
        return "Unknown"

    async def _determine_apply_type(self) -> ApplyType:
        """Determine if the job uses Easy Apply or external application."""
        try:
            # Look for apply button
            apply_button = self._page.locator(
                "button:has-text('Apply'), a:has-text('Apply')"
            ).first

            if not await apply_button.is_visible(timeout=5000):
                return ApplyType.UNKNOWN

            # Check if the button has indicators of external apply
            href = await apply_button.get_attribute("href")
            if href and "naukri.com" not in href:
                return ApplyType.EXTERNAL

            # Check button text for Easy Apply indicators
            text = await apply_button.text_content()
            if text:
                lower_text = text.lower()
                if "easy apply" in lower_text or "apply on company" not in lower_text:
                    return ApplyType.EASY_APPLY

            return ApplyType.EASY_APPLY
        except Exception:
            return ApplyType.UNKNOWN
