"""CLI entry point for Naukri auto-apply bot."""

import asyncio
import os
import sys
from pathlib import Path

import click

from naukri_apply.config import load_config


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
def apply_command(config_path, urls_file, urls):
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

    # Run the async apply logic
    try:
        asyncio.run(_run_apply(config_path, all_urls))
    except KeyboardInterrupt:
        click.echo("\nInterrupted by user. Shutting down gracefully.")
        sys.exit(0)


async def _run_apply(config_path: str, urls: list[str]) -> None:
    """Main async logic for applying to jobs."""
    from naukri_apply.applicator import JobApplicator
    from naukri_apply.browser import BrowserManager
    from naukri_apply.easy_apply import EasyApplyHandler
    from naukri_apply.external_apply import ExternalApplyHandler
    from naukri_apply.logger import CSVLogger
    from naukri_apply.models import ApplyType, ApplicationStatus

    config = load_config(config_path)
    logger = CSVLogger(config.output_csv)

    total = len(urls)
    applied = 0
    failed = 0
    skipped = 0

    click.echo(f"Starting application process for {total} job(s)...")

    async with BrowserManager(config) as browser:
        page = await browser.ensure_page()

        for i, url in enumerate(urls, 1):
            click.echo(f"\n[{i}/{total}] Processing: {url}")

            try:
                applicator = JobApplicator(page, config)
                job = await applicator.process_job(url)

                click.echo(f"  Title: {job.job_title}")
                click.echo(f"  Company: {job.company_name}")
                click.echo(f"  Location: {job.location}")
                click.echo(f"  Type: {job.apply_type.value}")

                if job.apply_type == ApplyType.EASY_APPLY:
                    handler = EasyApplyHandler(page, config)
                elif job.apply_type == ApplyType.EXTERNAL:
                    handler = ExternalApplyHandler(page, config)
                else:
                    from naukri_apply.models import ApplicationResult

                    result = ApplicationResult(
                        job=job,
                        status=ApplicationStatus.SKIPPED,
                        notes="Could not determine apply type",
                    )
                    logger.log(result)
                    skipped += 1
                    click.echo(f"  Status: SKIPPED (unknown apply type)")
                    continue

                result = handler.apply(job)
                result = await result
                logger.log(result)

                if result.status == ApplicationStatus.APPLIED:
                    applied += 1
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
                click.echo(f"  Error: {str(e)}")

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
