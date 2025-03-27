import asyncio
import logging
from playwright.async_api import async_playwright
from src.agents.browser.utils.browser_wrapper import BrowserWrapper
from src.agents.browser.planner.openai_gpt import OpenAIGPT
from src.agents.browser.utils.page_extraction_llm import OpenAIPageExtractionLLM
from src.agents.browser.services.orchestrator import ai_web_scraper

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

async def main():
    user_prompt = "What is the CPI index of Kerala for January 2025?"
    async with async_playwright() as playwright:
        browser_instance = await playwright.chromium.launch(
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--disable-background-timer-throttling',
                '--disable-popup-blocking',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-window-activation',
                '--disable-focus-on-load',
                '--no-first-run',
                '--no-default-browser-check',
                '--no-startup-window',
                '--window-position=0,0',
            ],
            headless=False
        )
        context = await browser_instance.new_context()
        page = await context.new_page()
        browser_wrapper = BrowserWrapper(page)

        # Instantiate the LLM classes
        gpt_llm = OpenAIGPT()
        page_extraction_llm = OpenAIPageExtractionLLM()

        final_result = await ai_web_scraper(user_prompt, browser_wrapper, page_extraction_llm, gpt_llm)
        logger.info("Final output: " + final_result)
        await browser_instance.close()

if __name__ == "__main__":
    asyncio.run(main())
