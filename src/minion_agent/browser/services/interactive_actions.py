import logging
import random
import asyncio
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

async def perform_page_interactions(browser, user_prompt: str) -> Dict[str, Any]:
    """
    Performs various interactive actions on the current page based on available UI elements.
    
    Args:
        browser: The browser wrapper instance
        user_prompt: The user query to contextualize interactions
        
    Returns:
        dict: Information about actions performed
    """
    page = await browser.get_current_page()
    actions_performed = []
    clickable_elements = []
    form_inputs = []
    
    # Step 1: Scroll down to load dynamic content
    try:
        logger.info("Scrolling down the page")
        await page.evaluate("""
            () => {
                window.scrollTo({
                    top: document.body.scrollHeight / 2,
                    behavior: 'smooth'
                });
            }
        """)
        await asyncio.sleep(1)  # Wait for content to load
        actions_performed.append("Scrolled down the page")
    except Exception as e:
        logger.warning(f"Error scrolling: {e}")
    
    # Step 2: Find and interact with clickable elements
    try:
        clickable_elements = await find_clickable_elements(page)
        if clickable_elements and len(clickable_elements) > 0:
            # Choose a relevant element based on the user prompt
            selected_element = await select_relevant_element(page, clickable_elements, user_prompt)
            if selected_element:
                try:
                    await selected_element.click()
                    element_text = await get_element_text(selected_element)
                    actions_performed.append(f"Clicked on element: {element_text}")
                    logger.info(f"Clicked on: {element_text}")
                    await asyncio.sleep(1)  # Wait for any changes to take effect
                except Exception as e:
                    logger.warning(f"Error clicking element: {e}")
    except Exception as e:
        logger.warning(f"Error finding clickable elements: {e}")
    
    # Step 3: Find and interact with form inputs
    try:
        form_inputs = await find_form_inputs(page)
        if form_inputs and len(form_inputs) > 0:
            # For text inputs, try to fill in relevant information
            for input_elem in form_inputs[:2]:  # Limit to first two inputs to avoid spam
                input_type = await input_elem.get_attribute("type") or ""
                if input_type in ["text", "search"]:
                    await input_elem.fill(user_prompt[:50])  # Use truncated user query
                    actions_performed.append("Filled in text input")
                    logger.info("Filled in text input with user query")
                    break  # Only fill one input to avoid spam
    except Exception as e:
        logger.warning(f"Error interacting with forms: {e}")
    
    # Initialize defaults
    clickable_count = 0
    form_inputs_count = 0
    
    # Simply use the variables we defined at the beginning of the function
    if clickable_elements is not None:
        clickable_count = len(clickable_elements)
    
    if form_inputs is not None:
        form_inputs_count = len(form_inputs)
    
    result = {
        "actions_performed": actions_performed,
        "elements_found": {
            "clickable": clickable_count,
            "form_inputs": form_inputs_count
        }
    }
    
    return result

async def find_clickable_elements(page):
    """Find clickable elements on the page."""
    return await page.query_selector_all('button, a[href], [role="button"], [onclick], input[type="button"], input[type="submit"]')

async def find_form_inputs(page):
    """Find form input elements on the page."""
    return await page.query_selector_all('input[type="text"], input[type="search"], textarea, input[type="email"]')

async def get_element_text(element):
    """Get the text of an element."""
    try:
        text = await element.text_content()
        if text:
            return text.strip()
        
        # If no direct text, try to get other attributes
        for attr in ["value", "placeholder", "title", "aria-label"]:
            attr_value = await element.get_attribute(attr)
            if attr_value:
                return attr_value.strip()
        
        return "Unknown element"
    except Exception:
        return "Unknown element"

async def select_relevant_element(page, elements, user_prompt: str):
    """Select the most relevant element based on the user prompt."""
    if not elements:
        return None
    
    # Get text content of all elements
    elements_with_text = []
    for element in elements:
        text = await get_element_text(element)
        if text and len(text.strip()) > 0:
            elements_with_text.append((element, text.lower()))
    
    if not elements_with_text:
        return random.choice(elements) if elements else None
    
    # Look for keywords in the user prompt
    keywords = user_prompt.lower().split()
    best_match = None
    best_score = 0
    
    for element, text in elements_with_text:
        score = sum(1 for keyword in keywords if keyword in text)
        if score > best_score:
            best_score = score
            best_match = element
    
    # If no good match, return a random element or one that might be a "Next" or "Continue" button
    if best_score == 0:
        next_buttons = [elem for elem, text in elements_with_text 
                        if any(term in text for term in ["next", "continue", "more", "show", "view", "read"])]
        if next_buttons:
            return next_buttons[0]
        return elements_with_text[0][0] if elements_with_text else None
    
    return best_match