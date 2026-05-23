"""Browser-use powered agent for Naukri job applications."""

import logging

from browser_use import Agent, BrowserSession, ChatGroq

from naukri_apply.config import AppConfig
from naukri_apply.models import (
    ApplicationResult,
    ApplicationStatus,
    ApplyType,
    JobListing,
    UserProfile,
)

logger = logging.getLogger(__name__)


class NaukriAgent:
    """Agent that uses browser-use for visual browser automation."""

    def __init__(self, config: AppConfig, browser: BrowserSession):
        self._config = config
        self._browser = browser
        self._llm = ChatGroq(
            model=config.llm.model,
            api_key=config.groq_api_key,
            temperature=config.llm.temperature,
        )
        self._max_steps = config.llm.max_steps

    def _build_profile_context(self, profile: UserProfile) -> str:
        """Build a text summary of user profile for the agent's task prompt."""
        parts = [f"Name: {profile.name}", f"Email: {profile.email}", f"Phone: {profile.phone}"]
        if profile.linkedin_url:
            parts.append(f"LinkedIn: {profile.linkedin_url}")
        if profile.experience_years is not None:
            parts.append(f"Experience: {profile.experience_years} years")
        if profile.current_company:
            parts.append(f"Current Company: {profile.current_company}")
        if profile.current_designation:
            parts.append(f"Current Role: {profile.current_designation}")
        if profile.notice_period:
            parts.append(f"Notice Period: {profile.notice_period}")
        if profile.resume_path:
            parts.append(f"Resume file path: {profile.resume_path}")
        return "\n".join(parts)

    async def apply_to_job(self, url: str, dry_run: bool = False) -> ApplicationResult:
        """Navigate to a job URL and apply using browser-use agent."""
        profile = self._config.user_profile
        profile_context = self._build_profile_context(profile)

        if dry_run:
            # In dry run mode, just extract job metadata without applying
            task = (
                f"Navigate to this job listing URL: {url}\n"
                "Extract the following information from the page:\n"
                "1. Job title\n"
                "2. Company name\n"
                "3. Location\n"
                "4. Whether it has an 'Easy Apply' button or redirects externally\n"
                "Return the information in this exact format:\n"
                "JOB_TITLE: <title>\n"
                "COMPANY: <company>\n"
                "LOCATION: <location>\n"
                "APPLY_TYPE: <easy_apply or external>\n"
                "Do NOT click any apply buttons."
            )
        else:
            task = (
                f"Navigate to this job listing URL: {url}\n\n"
                "Your goal is to apply to this job. Follow these steps:\n"
                "1. First, extract the job title, company name, and location from the page.\n"
                "2. Look for an 'Apply' or 'Easy Apply' button and click it.\n"
                "3. If a modal or form appears with screening questions, answer them using "
                "the applicant's profile below.\n"
                "4. If the application redirects to an external site (like Greenhouse, Lever, "
                "Workday, or a company career page), "
                "follow the redirect and fill out the application form there.\n"
                "5. Fill in all form fields using the applicant's profile information.\n"
                "6. If there is a resume/CV upload field, upload the file from the path "
                "specified below.\n"
                "7. Submit the application.\n"
                "8. Confirm whether the application was submitted successfully.\n\n"
                f"APPLICANT PROFILE:\n{profile_context}\n\n"
                "After completing, return the result in this exact format:\n"
                "JOB_TITLE: <title>\n"
                "COMPANY: <company>\n"
                "LOCATION: <location>\n"
                "APPLY_TYPE: <easy_apply or external>\n"
                "STATUS: <applied, failed, or external_partial>\n"
                "NOTES: <brief description of what happened>"
            )

        try:
            agent = Agent(
                task=task,
                llm=self._llm,
                browser=self._browser,
            )
            history = await agent.run(max_steps=self._max_steps)
            result_text = history.final_result() or ""

            # Parse the agent's result
            job_info = self._parse_result(result_text, url)

            if dry_run:
                return ApplicationResult(
                    job=job_info,
                    status=ApplicationStatus.SKIPPED,
                    notes="Dry run - no application submitted",
                )

            status = self._determine_status(result_text)
            notes = self._extract_notes(result_text)

            return ApplicationResult(
                job=job_info,
                status=status,
                notes=notes,
            )

        except Exception as e:
            logger.debug("Agent apply_to_job failed: %s", e)
            job = JobListing(
                company_name="Unknown",
                job_title="Unknown",
                location="Unknown",
                url=url,
                apply_type=ApplyType.UNKNOWN,
            )
            return ApplicationResult(
                job=job,
                status=ApplicationStatus.FAILED,
                notes=f"Agent error: {str(e)}",
            )

    async def direct_apply(self, job: JobListing) -> ApplicationResult:
        """Search Google for the company's career page and apply directly."""
        profile = self._config.user_profile
        profile_context = self._build_profile_context(profile)

        task = (
            f"Search Google for '{job.company_name} {job.job_title} careers apply' "
            "and find the company's career page or direct job application page.\n\n"
            "Steps:\n"
            "1. Go to Google and search for the company's career page with the job title.\n"
            "2. Click on the most relevant result (the company's official careers page).\n"
            "3. Find the specific job listing or an application form.\n"
            "4. Fill out the application form with the applicant's information.\n"
            "5. Submit the application.\n\n"
            f"APPLICANT PROFILE:\n{profile_context}\n\n"
            "After completing, return the result in this format:\n"
            "STATUS: <applied or failed>\n"
            "NOTES: <brief description of what happened>"
        )

        try:
            agent = Agent(
                task=task,
                llm=self._llm,
                browser=self._browser,
            )
            history = await agent.run(max_steps=self._max_steps)
            result_text = history.final_result() or ""

            status_str = self._extract_field(result_text, "STATUS").lower()
            if "applied" in status_str:
                status = ApplicationStatus.DIRECT_APPLIED
            else:
                status = ApplicationStatus.FAILED

            notes = self._extract_field(result_text, "NOTES") or f"Direct apply on {job.company_name}"

            return ApplicationResult(
                job=job,
                status=status,
                notes=notes,
            )
        except Exception as e:
            logger.debug("Agent direct_apply failed: %s", e)
            return ApplicationResult(
                job=job,
                status=ApplicationStatus.FAILED,
                notes=f"Direct apply error: {str(e)}",
            )

    async def check_login_status(self) -> bool:
        """Check if the browser session is logged in to Naukri.com."""
        task = (
            "Navigate to https://www.naukri.com and check if the user is logged in.\n"
            "Look for indicators like a user profile icon, 'My Naukri' link, or user menu.\n"
            "Return exactly one word: 'LOGGED_IN' if logged in, or 'NOT_LOGGED_IN' if not."
        )
        try:
            agent = Agent(
                task=task,
                llm=self._llm,
                browser=self._browser,
            )
            history = await agent.run(max_steps=10)
            result_text = (history.final_result() or "").upper()
            return "LOGGED_IN" in result_text and "NOT_LOGGED_IN" not in result_text
        except Exception as e:
            logger.debug("check_login_status failed: %s", e)
            return False

    def _parse_result(self, text: str, url: str) -> JobListing:
        """Parse structured fields from agent's text response."""
        job_title = self._extract_field(text, "JOB_TITLE") or "Unknown"
        company = self._extract_field(text, "COMPANY") or "Unknown"
        location = self._extract_field(text, "LOCATION") or "Unknown"
        apply_type_str = self._extract_field(text, "APPLY_TYPE") or "unknown"

        if "easy" in apply_type_str.lower():
            apply_type = ApplyType.EASY_APPLY
        elif "external" in apply_type_str.lower():
            apply_type = ApplyType.EXTERNAL
        elif "direct" in apply_type_str.lower():
            apply_type = ApplyType.DIRECT
        else:
            apply_type = ApplyType.UNKNOWN

        return JobListing(
            company_name=company,
            job_title=job_title,
            location=location,
            url=url,
            apply_type=apply_type,
        )

    def _determine_status(self, text: str) -> ApplicationStatus:
        """Determine application status from agent response text."""
        status_str = self._extract_field(text, "STATUS") or ""
        lower = status_str.lower()
        if "applied" in lower and "partial" not in lower:
            return ApplicationStatus.APPLIED
        elif "partial" in lower or "external_partial" in lower:
            return ApplicationStatus.EXTERNAL_PARTIAL
        elif "failed" in lower:
            return ApplicationStatus.FAILED
        elif "skipped" in lower:
            return ApplicationStatus.SKIPPED
        # If no clear status, check the full text for success indicators
        full_lower = text.lower()
        if "successfully" in full_lower or "submitted" in full_lower:
            return ApplicationStatus.APPLIED
        return ApplicationStatus.FAILED

    def _extract_notes(self, text: str) -> str:
        """Extract NOTES field from agent response."""
        return self._extract_field(text, "NOTES") or ""

    @staticmethod
    def _extract_field(text: str, field_name: str) -> str:
        """Extract a field value from 'FIELD: value' format text."""
        for line in text.split("\n"):
            if line.strip().upper().startswith(f"{field_name.upper()}:"):
                return line.split(":", 1)[1].strip()
        return ""
