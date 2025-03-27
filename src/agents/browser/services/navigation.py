import asyncio
import logging

logger = logging.getLogger(__name__)

async def go_to_url(url: str, browser) -> str:
    """
    Navigate to the specified URL.
    """
    page = await browser.get_current_page()
    try:
        await page.goto(url)
        await page.wait_for_load_state()
        logger.info(f'Navigated to {url}')
        return f'Navigated to {url}'
    except Exception as e:
        logger.error(f"Navigation to {url} failed: {e}")
        raise

async def wait_seconds(seconds: int = 3) -> str:
    """
    Wait for the specified number of seconds.
    """
    logger.info(f'Waiting for {seconds} seconds.')
    await asyncio.sleep(seconds)
    return f'Waited for {seconds} seconds.'
