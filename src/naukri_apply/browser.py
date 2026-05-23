"""Browser session management using Playwright."""

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from naukri_apply.config import AppConfig


class BrowserManager:
    """Manages Playwright browser lifecycle with persistent context for session reuse."""

    def __init__(self, config: AppConfig):
        self._config = config
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def __aenter__(self) -> "BrowserManager":
        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self._config.user_data_dir),
            headless=self._config.headless,
            slow_mo=self._config.slow_mo,
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._context:
            await self._context.close()
            self._context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._page = None

    @property
    def page(self) -> Page:
        """Return the first open page or create a new one."""
        if self._context is None:
            raise RuntimeError("BrowserManager is not initialized. Use as async context manager.")
        if self._context.pages:
            return self._context.pages[0]
        raise RuntimeError("No pages available. Call ensure_page() first.")

    async def ensure_page(self) -> Page:
        """Ensure at least one page exists and return it."""
        if self._context is None:
            raise RuntimeError("BrowserManager is not initialized. Use as async context manager.")
        if self._context.pages:
            return self._context.pages[0]
        page = await self._context.new_page()
        return page

    @property
    def context(self) -> BrowserContext:
        """Return the browser context."""
        if self._context is None:
            raise RuntimeError("BrowserManager is not initialized. Use as async context manager.")
        return self._context

    async def is_logged_in(self) -> bool:
        """Navigate to naukri.com and check for logged-in indicators."""
        page = await self.ensure_page()
        try:
            await page.goto("https://www.naukri.com", timeout=30000)
            # Check for profile/user menu elements that indicate a logged-in session
            logged_in_selectors = [
                "a.nI-gNb-drawer__icon",
                "[class*='user-icon']",
                "[class*='profile-icon']",
                "div.nI-gNb-header__right-info",
                "a[href*='/mnjuser/profile']",
            ]
            for selector in logged_in_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.is_visible(timeout=3000):
                        return True
                except Exception:
                    continue
            return False
        except Exception:
            return False
