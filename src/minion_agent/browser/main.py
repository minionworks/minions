import asyncio
import logging
import argparse
from typing import Optional, Union
from playwright.async_api import async_playwright
from langchain_openai import ChatOpenAI
from langchain_core.language_models.base import BaseLanguageModel
from .utils.browser_wrapper import BrowserWrapper
from .utils.page_extraction_llm import OpenAIPageExtractionLLM
from .services.orchestrator import ai_web_scraper
from .utils.mcp_planner import MCPPlanner


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

class MinionAgent:
    def __init__(
        self,
        task: str,
        llm: Optional[Union[BaseLanguageModel, ChatOpenAI]] = None,
        headless: bool = False
    ):
        """
        Initialize the Agent with a task and configuration.
        
        Args:
            task: The user-defined task or prompt
            llm: A language model instance (e.g., ChatOpenAI) that implements an 'analyze' method.
                 If not provided, will create a default ChatOpenAI instance
            headless: Whether to run browser in headless mode
        """
        self.task = task
        self.headless = headless
        
        # Initialize LLM
        if llm is None:
            raise ValueError("LLM instance must be provided")
        self.llm = llm
        self.result = None

    async def run(self):
        """
        Set up Playwright, create the browser context, and run the orchestrator with the provided task.
        Uses the planning LLM (self.llm) and instantiates an extraction LLM for function calling.
        """
        async with async_playwright() as playwright:
            browser_instance = await playwright.chromium.launch(
                args=[
                    '--no-sandbox',
                    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
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
                headless=self.headless
            )
            context = await browser_instance.new_context()
            page = await context.new_page()
            browser_wrapper = BrowserWrapper(page)
            mcp_planner = MCPPlanner(self.llm)

            # Instantiate the extraction LLM (for function calling)
            extraction_llm = OpenAIPageExtractionLLM(llm=self.llm)
            try:
                # Run the orchestrator with MCP planner
                self.result = await ai_web_scraper(
                    self.task,
                    browser_wrapper,
                    extraction_llm,
                    self.llm,
                    mcp_planner
                )
            except Exception as e:
                logger.error(f"Error in web scraper: {e}")
                self.result = f"An error occurred during web scraping: {str(e)}"
            finally:
                await context.close()
                await browser_instance.close()
        
        return self.result

            # result = await ai_web_scraper(self.task, browser_wrapper, extraction_llm, self.llm)
            # logger.info("Final output: " + result)
            # await browser_instance.close()
            # return result

# def main():
#     parser = argparse.ArgumentParser(description='Minion Works - AI-powered web automation')
#     parser.add_argument('task', help='The task or prompt to execute')
#     parser.add_argument('--debug', action='store_true', help='Enable debug logging')
#     parser.add_argument('--show-browser', action='store_true', help='Show browser window (headless mode)')
#     args = parser.parse_args()

#     if args.debug:
#         logging.getLogger().setLevel(logging.DEBUG)

#     # Create LLM instance
#     llm = ChatOpenAI(model="gpt-4o")
    
#     agent = MinionAgent(
#         task=args.task,
#         llm=llm,
#         headless=True
#     )
#     result = asyncio.run(agent.run())
#     print(result)

# if __name__ == '__main__':
#     main()

