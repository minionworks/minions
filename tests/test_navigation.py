import pytest
from src.minion_agent.browser.services.navigation import go_to_url, wait_seconds

class DummyPage:
    async def goto(self, url):
        self.url = url
    async def wait_for_load_state(self, state="load"):
        pass

class DummyBrowser:
    def __init__(self):
        self.page = DummyPage()
    async def get_current_page(self):
        return self.page

@pytest.mark.asyncio
async def test_wait_seconds():
    result = await wait_seconds(1)
    assert "Waited for 1 seconds" in result

@pytest.mark.asyncio
async def test_go_to_url():
    dummy_browser = DummyBrowser()
    result = await go_to_url("http://example.com", dummy_browser)
    assert "Navigated to http://example.com" in result
