import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)

class BrowserWrapper:
    """
    A simple wrapper around a Playwright page with additional navigation helpers.
    """
    def __init__(self, page: Page):
        self.page = page

    async def get_current_page(self) -> Page:
        return self.page

    async def go_back(self) -> None:
        page = await self.get_current_page()
        try:
            await page.go_back(timeout=10000)
            await page.wait_for_load_state('load')
            logger.info("Went back successfully.")
        except Exception as e:
            logger.error(f"Go back failed: {e}")
            raise

    async def refresh_page(self) -> None:
        page = await self.get_current_page()
        try:
            await page.reload()
            await page.wait_for_load_state('load')
            logger.info("Page refreshed successfully.")
        except Exception as e:
            logger.error(f"Page refresh failed: {e}")
            raise
