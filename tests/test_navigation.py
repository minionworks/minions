import pytest
from playwright.async_api import async_playwright
from src.utils.browser_wrapper import BrowserWrapper
from src.services.navigation import go_to_url

@pytest.mark.asyncio
async def test_go_to_url():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        browser_wrapper = BrowserWrapper(page)

        # Test navigating to a valid URL
        url = "https://example.com"
        result = await go_to_url({"url": url}, browser_wrapper)
        assert "Navigated to" in result

        # Clean up
        await browser.close()