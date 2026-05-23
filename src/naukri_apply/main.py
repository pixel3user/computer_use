"""CLI entry point for Naukri auto-apply bot."""

import asyncio
import logging
import os
import sys
from pathlib import Path

import click

from naukri_apply.config import load_config

logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Naukri.com auto-apply bot - Automate job applications."""
    pass


@cli.command("apply")
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    help="Path to config YAML file (default: NAUKRI_CONFIG_PATH env var or config.yaml)",
)
@click.option(
    "--urls-file",
    "-f",
    "urls_file",
    default=None,
    help="Path to file containing job URLs (one per line)",
)
@click.option(
    "--url",
    "-u",
    "urls",
    multiple=True,
    help="Single job URL (can be repeated)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Navigate and extract metadata but do not click any apply buttons",
)
def apply_command(config_path, urls_file, urls, dry_run):
    """Apply to jobs from provided URLs."""
    # Resolve config path
    if config_path is None:
        config_path = os.environ.get("NAUKRI_CONFIG_PATH", "config.yaml")

    # Collect all URLs
    all_urls = list(urls)

    if urls_file:
        urls_file_path = Path(urls_file)
        if not urls_file_path.exists():
            click.echo(f"Error: URLs file not found: {urls_file}", err=True)
            sys.exit(1)
        with open(urls_file_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    all_urls.append(line)

    if not all_urls:
        click.echo("Error: No URLs provided. Use --url or --urls-file.", err=True)
        sys.exit(1)

    if dry_run:
        click.echo("DRY RUN MODE: No applications will be submitted.")

    # Run the async apply logic
    try:
        asyncio.run(_run_apply(config_path, all_urls, dry_run=dry_run))
    except KeyboardInterrupt:
        click.echo("\nInterrupted by user. Shutting down gracefully.")
        sys.exit(0)


async def _run_apply(config_path: str, urls: list[str], dry_run: bool = False) -> None:
    """Main async logic for applying to jobs."""
    from naukri_apply.applicator import JobApplicator
    from naukri_apply.browser import BrowserManager
    from naukri_apply.easy_apply import EasyApplyHandler
    from naukri_apply.external_apply import ExternalApplyHandler
    from naukri_apply.logger import CSVLogger
    from naukri_apply.models import ApplyType, ApplicationStatus

    config = load_config(config_path)
    csv_logger = CSVLogger(config.output_csv)

    # Initialize LLM agent if configured
    llm_agent = None
    if config.llm.enabled and config.groq_api_key:
        try:
            from naukri_apply.llm_agent import LLMAgent

            llm_agent = LLMAgent(config)
            click.echo("LLM agent initialized (Groq API)")
        except Exception as e:
            logger.debug("Failed to initialize LLM agent: %s", e)
            click.echo(f"Warning: LLM agent not available: {e}")

    total = len(urls)
    applied = 0
    failed = 0
    skipped = 0
    naukri_application_count = 0
    naukri_attempt_count = 0
    switched_to_direct = False
    # If consecutive failures exceed this threshold, switch to direct mode
    failure_threshold = max(10, config.quota.max_naukri_applications // 5)

    click.echo(f"Starting application process for {total} job(s)...")

    async with BrowserManager(config) as browser:
        page = await browser.ensure_page()

        for i, url in enumerate(urls, 1):
            click.echo(f"\n[{i}/{total}] Processing: {url}")

            # Check if quota reached and switch to direct apply
            if (
                not switched_to_direct
                and config.quota.enable_direct_apply
                and llm_agent
                and (
                    naukri_application_count >= config.quota.max_naukri_applications
                    or naukri_attempt_count >= config.quota.max_naukri_applications + failure_threshold
                )
            ):
                switched_to_direct = True
                click.echo(
                    f"\nQuota reached ({naukri_application_count} applications, "
                    f"{naukri_attempt_count} attempts). "
                    "Switching to direct company applications."
                )

            try:
                applicator = JobApplicator(page, config)
                job = await applicator.process_job(url)

                click.echo(f"  Title: {job.job_title}")
                click.echo(f"  Company: {job.company_name}")
                click.echo(f"  Location: {job.location}")
                click.echo(f"  Type: {job.apply_type.value}")

                if dry_run:
                    click.echo(f"  [DRY RUN] Would apply via: {job.apply_type.value}")
                    skipped += 1
                    continue

                # Use DirectApplyHandler if quota reached
                if switched_to_direct:
                    from naukri_apply.direct_apply import DirectApplyHandler

                    handler = DirectApplyHandler(page, config, llm_agent)
                    result = await handler.apply(job)
                    csv_logger.log(result)

                    if result.status == ApplicationStatus.DIRECT_APPLIED:
                        applied += 1
                        click.echo(f"  Status: DIRECT_APPLIED")
                    else:
                        failed += 1
                        click.echo(f"  Status: FAILED - {result.notes}")
                    continue

                if job.apply_type == ApplyType.EASY_APPLY:
                    handler = EasyApplyHandler(page, config, llm_agent=llm_agent)
                elif job.apply_type == ApplyType.EXTERNAL:
                    handler = ExternalApplyHandler(page, config, llm_agent=llm_agent)
                else:
                    from naukri_apply.models import ApplicationResult

                    result = ApplicationResult(
                        job=job,
                        status=ApplicationStatus.SKIPPED,
                        notes="Could not determine apply type",
                    )
                    csv_logger.log(result)
                    skipped += 1
                    click.echo(f"  Status: SKIPPED (unknown apply type)")
                    continue

                result = handler.apply(job)
                result = await result
                csv_logger.log(result)

                # Count every attempt (success or failure) toward the attempt threshold
                naukri_attempt_count += 1

                if result.status == ApplicationStatus.APPLIED:
                    applied += 1
                    naukri_application_count += 1
                    click.echo(f"  Status: APPLIED")
                elif result.status == ApplicationStatus.EXTERNAL_PARTIAL:
                    applied += 1
                    click.echo(f"  Status: EXTERNAL_PARTIAL")
                elif result.status == ApplicationStatus.FAILED:
                    failed += 1
                    click.echo(f"  Status: FAILED - {result.notes}")
                else:
                    skipped += 1
                    click.echo(f"  Status: {result.status.value}")

            except Exception as e:
                failed += 1
                logger.debug("Error processing URL %s: %s", url, e)
                click.echo(f"  Error: {str(e)}")

            # Rate limiting: wait between applications
            if i < total:
                delay = config.delay_between_applications
                if delay > 0 and not dry_run:
                    logger.debug("Waiting %.1f seconds before next application", delay)
                    await asyncio.sleep(delay)

    click.echo(f"\n{'='*50}")
    click.echo(f"Summary: {total} processed, {applied} applied, {failed} failed, {skipped} skipped")


@cli.command("check-session")
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    help="Path to config YAML file",
)
def check_session_command(config_path):
    """Check if the browser session is logged in to Naukri.com."""
    if config_path is None:
        config_path = os.environ.get("NAUKRI_CONFIG_PATH", "config.yaml")

    try:
        asyncio.run(_run_check_session(config_path))
    except KeyboardInterrupt:
        click.echo("\nInterrupted by user.")
        sys.exit(0)


async def _run_check_session(config_path: str) -> None:
    """Check login status."""
    from naukri_apply.browser import BrowserManager

    config = load_config(config_path)

    click.echo("Checking login status...")

    async with BrowserManager(config) as browser:
        logged_in = await browser.is_logged_in()

        if logged_in:
            click.echo("Status: Logged in to Naukri.com")
        else:
            click.echo("Status: NOT logged in. Please log in manually first.")


if __name__ == "__main__":
    cli()
