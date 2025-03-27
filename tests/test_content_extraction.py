import pytest
from src.services.content_extraction import extract_content
from src.utils.browser_wrapper import BrowserWrapper
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_extract_content():
    # Arrange
    mock_page = AsyncMock()
    mock_page.content.return_value = "<html><body><h1>Test Title</h1><p>Test content for extraction.</p></body></html>"
    browser_wrapper = BrowserWrapper(mock_page)
    mock_llm = AsyncMock()
    mock_llm.invoke.return_value = AsyncMock(content='{"extracted": "Test content for extraction."}')
    
    goal = "Extract main content"
    
    # Act
    result = await extract_content(goal, browser_wrapper, mock_llm)
    
    # Assert
    assert "Extracted from page:" in result
    assert "Test content for extraction." in result