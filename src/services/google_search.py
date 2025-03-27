

async def search_google(params, browser):
    """
    Performs a Google search and extracts the URLs and titles from the search results.
    """
    page = await browser.get_current_page()
    query = params.get("query")
    url = f'https://www.google.com/search?q={query}&udm=14'
    await page.goto(url)
    await page.wait_for_load_state()
    
    search_results = await page.evaluate('''() => {
        return Array.from(document.querySelectorAll('a h3')).map(h => ({
            title: h.innerText,
            url: h.parentElement.href
        })).slice(0, 10);
    }''')
    
    msg = f'🔍  Searched for "{query}" in Google'
    print("search_google msg:", msg)
    return search_results