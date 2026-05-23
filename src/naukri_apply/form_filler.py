"""Utility functions for detecting and filling form fields."""

import logging

from playwright.async_api import Locator, Page

logger = logging.getLogger(__name__)


# Mapping of field types to lists of CSS/text selectors to try
FIELD_PATTERNS: dict[str, list[str]] = {
    "name": [
        "label:has-text('Name') + input",
        "label:has-text('Full Name') + input",
        "input[name*='name' i]",
        "input[id*='name' i]",
        "input[placeholder*='name' i]",
        "input[aria-label*='name' i]",
    ],
    "email": [
        "label:has-text('Email') + input",
        "input[name*='email' i]",
        "input[id*='email' i]",
        "input[type='email']",
        "input[placeholder*='email' i]",
        "input[aria-label*='email' i]",
    ],
    "phone": [
        "label:has-text('Phone') + input",
        "label:has-text('Mobile') + input",
        "input[name*='phone' i]",
        "input[id*='phone' i]",
        "input[type='tel']",
        "input[placeholder*='phone' i]",
        "input[aria-label*='phone' i]",
    ],
    "linkedin": [
        "label:has-text('LinkedIn') + input",
        "input[name*='linkedin' i]",
        "input[id*='linkedin' i]",
        "input[placeholder*='linkedin' i]",
        "input[aria-label*='linkedin' i]",
    ],
    "resume": [
        "input[type='file'][name*='resume' i]",
        "input[type='file'][id*='resume' i]",
        "input[type='file'][name*='cv' i]",
        "input[type='file'][id*='cv' i]",
        "input[type='file'][accept*='pdf']",
        "input[type='file']",
    ],
    "experience": [
        "label:has-text('Experience') + input",
        "label:has-text('Years') + input",
        "input[name*='experience' i]",
        "input[id*='experience' i]",
        "input[placeholder*='experience' i]",
        "input[aria-label*='experience' i]",
    ],
    "company": [
        "label:has-text('Company') + input",
        "label:has-text('Current Company') + input",
        "input[name*='company' i]",
        "input[id*='company' i]",
        "input[placeholder*='company' i]",
        "input[aria-label*='company' i]",
    ],
    "password": [
        "input[type='password']",
        "input[name*='password' i]",
        "input[id*='password' i]",
    ],
}


async def find_field(page: Page, field_type: str) -> Locator | None:
    """Find a form field by trying multiple selector patterns.

    Returns the first visible match or None if no field is found.
    """
    patterns = FIELD_PATTERNS.get(field_type, [])
    for pattern in patterns:
        try:
            locator = page.locator(pattern).first
            if await locator.is_visible(timeout=2000):
                return locator
        except Exception as e:
            logger.debug("Field '%s' pattern '%s' failed: %s", field_type, pattern, e)
            continue
    return None


async def fill_text_field(locator: Locator, value: str) -> None:
    """Clear a text field and type the given value with a small delay."""
    await locator.click()
    await locator.fill("")
    await locator.type(value, delay=50)


async def upload_file(page: Page, locator: Locator, file_path: str) -> None:
    """Upload a file using the file input element."""
    await locator.set_input_files(file_path)


async def select_dropdown(locator: Locator, value: str) -> None:
    """Select a dropdown option by value or visible text.

    Tries select_option first, then falls back to clicking and selecting
    visible option text.
    """
    try:
        await locator.select_option(label=value, timeout=3000)
    except Exception as e:
        logger.debug("select_option failed for value '%s': %s", value, e)
        try:
            await locator.click()
            option = locator.page.locator(f"text={value}").first
            await option.click(timeout=3000)
        except Exception as e2:
            logger.debug("Fallback dropdown selection failed: %s", e2)
