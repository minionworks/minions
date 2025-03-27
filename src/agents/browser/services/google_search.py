import logging

logger = logging.getLogger(__name__)

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
