"""Browser session management using browser-use."""

from browser_use import BrowserProfile, BrowserSession

from naukri_apply.config import AppConfig


class BrowserManager:
    """Manages browser-use BrowserSession lifecycle with persistent context."""

    def __init__(self, config: AppConfig):
        self._config = config
        self._profile = BrowserProfile(
            user_data_dir=str(config.user_data_dir),
            headless=config.headless,
            # wait_between_actions maps to slow_mo concept
            wait_between_actions=config.slow_mo / 1000.0,  # convert ms to seconds
        )
        self._browser: BrowserSession | None = None

    async def __aenter__(self) -> "BrowserManager":
        self._browser = BrowserSession(browser_profile=self._profile)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            await self._browser.close()
            self._browser = None

    @property
    def browser(self) -> BrowserSession:
        if self._browser is None:
            raise RuntimeError("BrowserManager not initialized. Use as async context manager.")
        return self._browser

    @property
    def profile(self) -> BrowserProfile:
        return self._profile
