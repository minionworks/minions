import logging
from typing import Any, Optional
from playwright.async_api import Page

logger = logging.getLogger(__name__)

class BrowserWrapper:
    """
    A wrapper for Playwright browser page to provide a consistent interface
    and handle common browser operations.
    """
    
    def __init__(self, page: Page):
        """
        Initialize the browser wrapper.
        
        Args:
            page: The Playwright page object
        """
        self.page = page
        self.current_page = page
    
    async def get_current_page(self) -> Page:
        """
        Get the current active page.
        
        Returns:
            Page: The current Playwright page
        """
        return self.current_page
    
    async def goto(self, url: str) -> None:
        """
        Navigate to a URL.
        
        Args:
            url: The URL to navigate to
        """
        await self.current_page.goto(url)
        await self.current_page.wait_for_load_state()
        logger.info(f"Navigated to {url}")
    
    async def get_url(self) -> str:
        """
        Get the current URL.
        
        Returns:
            str: The current URL
        """
        return self.current_page.url
    
    async def get_title(self) -> str:
        """
        Get the current page title.
        
        Returns:
            str: The current page title
        """
        return await self.current_page.title()
    
    async def go_back(self) -> None:
        """
        Navigate to the previous page in history.
        """
        await self.current_page.go_back()
        await self.current_page.wait_for_load_state()
        logger.info("Navigated back")
    
    async def screenshot(self, path: Optional[str] = None) -> bytes:
        """
        Take a screenshot of the current page.
        
        Args:
            path: Optional path to save the screenshot
            
        Returns:
            bytes: The screenshot as bytes
        """
        return await self.current_page.screenshot(path=path)
    
    async def evaluate(self, script: str, arg: Any = None) -> Any:
        """
        Evaluate JavaScript in the context of the page.
        
        Args:
            script: JavaScript to execute
            arg: Optional argument to pass to the script
            
        Returns:
            Any: The result of the evaluation
        """
        return await self.current_page.evaluate(script, arg)
    
    async def query_selector(self, selector: str) -> Any:
        """
        Query for an element with the given selector.
        
        Args:
            selector: The selector to query
            
        Returns:
            Any: The element if found, None otherwise
        """
        return await self.current_page.query_selector(selector)