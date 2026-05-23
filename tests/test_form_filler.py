"""Tests for form_filler utility functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from naukri_apply.form_filler import (
    FIELD_PATTERNS,
    fill_text_field,
    find_field,
    select_dropdown,
    upload_file,
)


class TestFieldPatterns:
    """Test the FIELD_PATTERNS dictionary structure."""

    def test_has_expected_field_types(self):
        expected_types = [
            "name",
            "email",
            "phone",
            "linkedin",
            "resume",
            "experience",
            "company",
            "password",
        ]
        for field_type in expected_types:
            assert field_type in FIELD_PATTERNS, f"Missing field type: {field_type}"

    def test_patterns_are_non_empty(self):
        for field_type, patterns in FIELD_PATTERNS.items():
            assert len(patterns) > 0, f"Empty patterns for: {field_type}"

    def test_patterns_are_strings(self):
        for field_type, patterns in FIELD_PATTERNS.items():
            for pattern in patterns:
                assert isinstance(pattern, str), (
                    f"Pattern for {field_type} is not a string: {pattern}"
                )

    def test_patterns_are_well_formed(self):
        """All patterns should be non-empty and contain selector syntax."""
        for field_type, patterns in FIELD_PATTERNS.items():
            for pattern in patterns:
                assert len(pattern) > 0, f"Empty pattern in {field_type}"
                # Should contain at least one selector indicator
                assert any(
                    char in pattern for char in [".", "#", "[", ":", "input", "label"]
                ), f"Pattern '{pattern}' in {field_type} looks malformed"

    def test_email_patterns_include_type_email(self):
        """Email field patterns should include input[type='email']."""
        email_patterns = FIELD_PATTERNS["email"]
        has_type_email = any("type='email'" in p or 'type="email"' in p for p in email_patterns)
        assert has_type_email, "Email patterns should include type='email' selector"

    def test_resume_patterns_include_file_input(self):
        """Resume field should use file input."""
        resume_patterns = FIELD_PATTERNS["resume"]
        has_file_type = any("type='file'" in p or 'type="file"' in p for p in resume_patterns)
        assert has_file_type, "Resume patterns should include file input selector"

    def test_phone_patterns_include_type_tel(self):
        """Phone field patterns should include input[type='tel']."""
        phone_patterns = FIELD_PATTERNS["phone"]
        has_type_tel = any("type='tel'" in p or 'type="tel"' in p for p in phone_patterns)
        assert has_type_tel, "Phone patterns should include type='tel' selector"


class TestFindField:
    """Test the find_field function with mocked Playwright page."""

    @pytest.mark.asyncio
    async def test_find_field_returns_visible_locator(self):
        mock_page = MagicMock()
        mock_locator = AsyncMock()
        mock_locator.is_visible = AsyncMock(return_value=True)

        mock_first = MagicMock()
        mock_first.is_visible = AsyncMock(return_value=True)

        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_first))

        result = await find_field(mock_page, "email")
        assert result is not None

    @pytest.mark.asyncio
    async def test_find_field_returns_none_when_not_visible(self):
        mock_page = MagicMock()
        mock_first = MagicMock()
        mock_first.is_visible = AsyncMock(return_value=False)
        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_first))

        result = await find_field(mock_page, "email")
        assert result is None

    @pytest.mark.asyncio
    async def test_find_field_returns_none_for_unknown_type(self):
        mock_page = MagicMock()
        result = await find_field(mock_page, "nonexistent_field")
        assert result is None

    @pytest.mark.asyncio
    async def test_find_field_handles_exceptions(self):
        mock_page = MagicMock()
        mock_first = MagicMock()
        mock_first.is_visible = AsyncMock(side_effect=Exception("Element detached"))
        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_first))

        result = await find_field(mock_page, "name")
        assert result is None


class TestFillTextField:
    """Test the fill_text_field function."""

    @pytest.mark.asyncio
    async def test_fill_text_field_clears_and_types(self):
        mock_locator = AsyncMock()
        await fill_text_field(mock_locator, "test@example.com")

        mock_locator.click.assert_called_once()
        mock_locator.fill.assert_called_once_with("")
        mock_locator.type.assert_called_once_with("test@example.com", delay=50)


class TestUploadFile:
    """Test the upload_file function."""

    @pytest.mark.asyncio
    async def test_upload_file_calls_set_input_files(self):
        mock_page = MagicMock()
        mock_locator = AsyncMock()
        await upload_file(mock_page, mock_locator, "/path/to/resume.pdf")

        mock_locator.set_input_files.assert_called_once_with("/path/to/resume.pdf")


class TestSelectDropdown:
    """Test the select_dropdown function."""

    @pytest.mark.asyncio
    async def test_select_dropdown_uses_select_option(self):
        mock_locator = AsyncMock()
        await select_dropdown(mock_locator, "5 years")

        mock_locator.select_option.assert_called_once_with(label="5 years", timeout=3000)

    @pytest.mark.asyncio
    async def test_select_dropdown_falls_back_to_click(self):
        mock_locator = AsyncMock()
        mock_locator.select_option = AsyncMock(side_effect=Exception("Not a select"))

        mock_option = AsyncMock()
        mock_page = MagicMock()
        mock_page.locator = MagicMock(return_value=MagicMock(first=mock_option))
        mock_locator.page = mock_page

        await select_dropdown(mock_locator, "5 years")

        mock_locator.click.assert_called_once()
