import pytest
from src.agents.browser.services.google_search import search_google, search_next_page

class DummyPage:
    async def goto(self, url):
        self.url = url
    async def wait_for_load_state(self):
        pass
    async def evaluate(self, script):
        # Simulate returning dummy search results.
        return [{"title": "Dummy", "url": "http://dummy.com"}]

class DummyBrowser:
    def __init__(self):
        self.page = DummyPage()
    async def get_current_page(self):
        return self.page
    async def query_selector(self, selector):
        return None  # Simulate no next page available.

@pytest.mark.asyncio
async def test_search_google():
    browser = DummyBrowser()
    results = await search_google("test", browser)
    assert isinstance(results, list)
    assert results[0]["url"] == "http://dummy.com"

@pytest.mark.asyncio
async def test_search_next_page():
    browser = DummyBrowser()
    results = await search_next_page(browser)
    # With dummy browser, no next page should be found.
    assert results == []
