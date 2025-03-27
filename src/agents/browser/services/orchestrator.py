import logging
from src.agents.browser.services.google_search import search_google, search_next_page
from src.agents.browser.services.navigation import go_to_url
from src.agents.browser.services.content_extraction import extract_content
from src.agents.browser.utils.helpers import save_output

logger = logging.getLogger(__name__)

async def ai_web_scraper(user_prompt: str, browser, page_extraction_llm, gpt_llm) -> str:
    """
    Orchestrates the web scraping:
      1. Perform a Google search.
      2. Iterate through search result URLs.
      3. For each URL, navigate and extract content using function calling.
      4. If extraction returns 'next_url', skip to the next link.
      5. If 'final', return the answer.
      6. If all links are exhausted, try the next page or finish.
    """
    search_results = await search_google(user_prompt, browser)
    current_index = 0

    while True:
        if current_index < len(search_results):
            current_url = search_results[current_index]["url"]
            logger.info(f"Processing URL {current_index+1}/{len(search_results)}: {current_url}")
            try:
                await go_to_url(current_url, browser)
            except Exception as e:
                logger.error(f"Navigation error for {current_url}: {e}. Attempting to go back and skip.")
                try:
                    await browser.go_back()
                except Exception:
                    pass
                current_index += 1
                continue

            try:
                extraction_result = await extract_content(user_prompt, browser, page_extraction_llm, target_selector="div#main")
            except Exception as e:
                logger.error(f"Extraction error for {current_url}: {e}")
                extraction_result = {"action": "next_url", "summary": "", "key_points": [], "context": "", "output": ""}

            action_type = extraction_result.get("action", "next_url")
            if action_type == "final":
                final_output = extraction_result.get("output", "Final outcome reached")
                save_output("final_output.txt", final_output)
                return final_output
            else:
                current_index += 1
                continue

        else:
            new_results = await search_next_page(browser)
            if new_results:
                search_results = new_results
                current_index = 0
                continue
            else:
                logger.info("No further search results available.")
                return "Scraper finished execution without a final outcome."
