import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.orchestrator import ai_web_scraper
from src.utils.browser_wrapper import BrowserWrapper
from src.utils.openai_gpt import OpenAIGPT
from src.utils.page_extraction_llm import OpenAIPageExtractionLLM

@pytest.mark.asyncio
async def test_ai_web_scraper(monkeypatch):
    user_prompt = "What are the latest trends in AI?"

    mock_browser = AsyncMock(spec=BrowserWrapper)
    mock_page_extraction_llm = AsyncMock(spec=OpenAIPageExtractionLLM)
    mock_gpt_llm = AsyncMock(spec=OpenAIGPT)

    mock_browser.get_current_page.return_value = MagicMock()
    mock_gpt_llm.analyze.side_effect = [
        {"action": "go_to_url", "url": "https://example.com"},
        {"action": "extract_content"},
        {"action": "final", "output": "Final summary of AI trends."}
    ]
    mock_page_extraction_llm.invoke.return_value.content = '{"summary": "AI is evolving."}'

    final_output = await ai_web_scraper(user_prompt, mock_browser, mock_page_extraction_llm, mock_gpt_llm)

    assert final_output == "Final summary of AI trends."
    mock_gpt_llm.analyze.assert_called()  # Ensure analyze was called
    mock_page_extraction_llm.invoke.assert_called()  # Ensure invoke was called