import pytest
from src.minion_agent.browser.services.content_extraction import extract_content

class DummyElement:
    async def inner_html(self):
        return "<div>Main Content</div>"

class DummyPage:
    async def query_selector(self, selector):
        if selector == "div#main":
            return DummyElement()
        return None
    async def content(self):
        return "<html>Fallback Content</html>"

class DummyBrowser:
    def __init__(self):
        self.page = DummyPage()
    async def get_current_page(self):
        return self.page

class DummyExtractionLLM:
    async def extract_with_function_call(self, page_content_markdown, question):
        # Simulate extraction returning a final result.
        return {"action": "final", "output": "Extracted Content", "summary": "", "key_points": [], "context": ""}

@pytest.mark.asyncio
async def test_extract_content():
    dummy_browser = DummyBrowser()
    dummy_llm = DummyExtractionLLM()
    result = await extract_content("Test Question", dummy_browser, dummy_llm, target_selector="div#main")
    assert result["action"] == "final"
    assert result["output"] == "Extracted Content"
