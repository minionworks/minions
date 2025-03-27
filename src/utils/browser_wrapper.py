class BrowserWrapper:
    """
    A simple wrapper to hold the current Playwright page.
    """
    def __init__(self, page):
        self.page = page

    async def get_current_page(self):
        return self.page