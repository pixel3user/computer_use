"""Tests for the BrowserManager class."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from naukri_apply.browser import BrowserManager


class TestBrowserManagerInit:
    @patch("naukri_apply.browser.BrowserProfile")
    @patch("naukri_apply.browser.BrowserSession")
    def test_browser_manager_creates_profile(
        self, MockBrowserSession, MockBrowserProfile, mock_app_config
    ):
        MockBrowserProfile.return_value = MagicMock()

        manager = BrowserManager(mock_app_config)

        MockBrowserProfile.assert_called_once_with(
            user_data_dir=str(mock_app_config.user_data_dir),
            headless=mock_app_config.headless,
            wait_between_actions=mock_app_config.slow_mo / 1000.0,
        )
        assert manager.profile is MockBrowserProfile.return_value

    @patch("naukri_apply.browser.BrowserProfile")
    def test_browser_manager_raises_when_not_initialized(
        self, MockBrowserProfile, mock_app_config
    ):
        MockBrowserProfile.return_value = MagicMock()

        manager = BrowserManager(mock_app_config)

        with pytest.raises(RuntimeError, match="not initialized"):
            _ = manager.browser


class TestBrowserManagerContextManager:
    @pytest.mark.asyncio
    @patch("naukri_apply.browser.BrowserProfile")
    @patch("naukri_apply.browser.BrowserSession")
    async def test_browser_manager_context_manager(
        self, MockBrowserSession, MockBrowserProfile, mock_app_config
    ):
        mock_session_instance = MagicMock()
        mock_session_instance.close = AsyncMock()
        MockBrowserSession.return_value = mock_session_instance
        MockBrowserProfile.return_value = MagicMock()

        manager = BrowserManager(mock_app_config)

        async with manager as ctx:
            assert ctx is manager
            assert ctx.browser is mock_session_instance
            MockBrowserSession.assert_called_once()

        mock_session_instance.close.assert_called_once()
