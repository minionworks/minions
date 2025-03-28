import logging
from openai import AsyncOpenAI
from src.config.settings import OPENAI_API_KEY

aclient = AsyncOpenAI(api_key=OPENAI_API_KEY)

logger = logging.getLogger(__name__)

async def refine_search_query(original_query: str) -> str:
    """
    Uses GPT to refine the raw user query into an optimized search query for Google.
    Returns the refined query as plain text.
    """
    system_message = {
    "role": "system",
    "content": (
        "You are an expert search query refiner. Your job is to transform a user's raw question into a concise and targeted search query that will yield highly relevant results on Google. "
        "If the input includes any output format instructions (like JSON, CSV, etc.), ignore them. "
        "Return only the refined search query in plain text with no additional commentary."
    )
}
    user_message = {
        "role": "user",
        "content": f"Original query: {original_query}"
    }
    response =await aclient.chat.completions.create(model="gpt-4o",
         messages=[system_message, user_message],
        temperature=0.0)
    refined_query = response.choices[0].message.content.strip()
    logger.info(f"Refined search query: {refined_query}")
    return refined_query

async def search_google(query: str, browser) -> list:
    """
    Perform a Google search and return the top search results.
    """
    page = await browser.get_current_page()
    search_url = f'https://www.google.com/search?q={query}&udm=14'
    await page.goto(search_url)
    await page.wait_for_load_state()
    results = await page.evaluate('''() => {
        return Array.from(document.querySelectorAll('a h3')).map(h => ({
            title: h.innerText,
            url: h.parentElement.href
        })).slice(0, 10);
    }''')
    logger.info(f'Searched for "{query}" on Google. Found {len(results)} results.')
    return results

async def search_next_page(browser) -> list:
    """
    Click the "Next" button on Google search results and return new results.
    """
    page = await browser.get_current_page()
    next_button = await page.query_selector('a#pnnext')
    if next_button:
        await next_button.click()
        await page.wait_for_load_state()
        new_results = await page.evaluate('''() => {
            return Array.from(document.querySelectorAll('a h3')).map(h => ({
                title: h.innerText,
                url: h.parentElement.href
            })).slice(0, 10);
        }''')
        logger.info("Loaded next page of search results.")
        return new_results
    else:
        logger.info("No next page found.")
        return []
