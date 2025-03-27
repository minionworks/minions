import pytest
from src.services.google_search import search_google
from src.utils.browser_wrapper import BrowserWrapper

@pytest.mark.asyncio
async def test_search_google(mocker):
    # Mocking the browser and page
    mock_page = mocker.Mock()
    mock_browser = BrowserWrapper(mock_page)

    # Mocking the page.evaluate method to return a predefined result
    mock_page.evaluate.return_value = [
        {"title": "Test Title 1", "url": "https://example.com/1"},
        {"title": "Test Title 2", "url": "https://example.com/2"},
    ]

    params = {"query": "test query"}
    
    # Call the search_google function
    results = await search_google(params, mock_browser)

    # Assertions to verify the results
    assert len(results) == 2
    assert results[0]["title"] == "Test Title 1"
    assert results[0]["url"] == "https://example.com/1"
    assert results[1]["title"] == "Test Title 2"
    assert results[1]["url"] == "https://example.com/2"