import asyncio
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from utils.browser_wrapper import BrowserWrapper
from utils.openai_gpt import OpenAIGPT
from utils.page_extraction_llm import OpenAIPageExtractionLLM
from services.orchestrator import ai_web_scraper

async def main():
    load_dotenv()
    user_prompt = "What are the latest trends in AI?"
    
    async with async_playwright() as p:
        browser_instance = await p.chromium.launch(headless=False)
        context = await browser_instance.new_context()
        page = await context.new_page()

        browser_wrapper = BrowserWrapper(page)
        gpt_llm = OpenAIGPT()
        page_extraction_llm = OpenAIPageExtractionLLM()

        final_output = await ai_web_scraper(user_prompt, browser_wrapper, page_extraction_llm, gpt_llm)
        print("Final output:", final_output)

        await browser_instance.close()

if __name__ == "__main__":
    asyncio.run(main())