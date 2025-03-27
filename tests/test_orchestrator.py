import pytest
from src.agents.browser.services.orchestrator import ai_web_scraper

class DummyPage:
    async def goto(self, url):
        self.url = url
    async def wait_for_load_state(self, state="load"):
        pass
    async def evaluate(self, script):
        return [{"title": "Dummy", "url": "http://dummy.com"}]

class DummyBrowser:
    def __init__(self):
        self.page = DummyPage()
    async def get_current_page(self):
        return self.page
    async def query_selector(self, selector):
        return None
    async def go_back(self):
        pass

class DummyExtractionLLM:
    async def extract_with_function_call(self, page_content_markdown, question):
        # Always return next_url to simulate going through links.
        return {"action": "next_url", "output": "", "summary": "", "key_points": [], "context": ""}

class DummyGPT:
    async def analyze(self, input_text):
        return {"action": "final", "output": "Final Answer"}

@pytest.mark.asyncio
async def test_ai_web_scraper():
    dummy_browser = DummyBrowser()
    dummy_llm = DummyExtractionLLM()
    dummy_gpt = DummyGPT()
    result = await ai_web_scraper("Test Question", dummy_browser, dummy_llm, dummy_gpt)
    # With dummy_llm always returning next_url, orchestrator should finish without a final outcome.
    assert "Scraper finished execution" in result
