

async def go_to_url(params, browser):
    """
    Navigates to the specified URL.
    """
    page = await browser.get_current_page()
    url = params.get("url")
    await page.goto(url)
    await page.wait_for_load_state()
    msg = f'🔗  Navigated to {url}'
    print("go_to_url msg:", msg)
    return msg