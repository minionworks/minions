import logging
import random
import asyncio
import json
from typing import Optional, List, Dict, Any, Tuple
import re
import os

# OpenAI client setup
HAS_OPENAI = False
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    logging.warning("OpenAI library not found, LLM-based element selection will be disabled")

logger = logging.getLogger(__name__)

class ElementSelector:
    """
    Uses LLM to intelligently select elements and generate input text
    """
    def __init__(self, model="gpt-4o"):
        self.model = model
        # Get API key from environment
        api_key = os.environ.get("OPENAI_API_KEY")
        
        # Check if OpenAI is available and API key is set
        if not HAS_OPENAI:
            logger.warning("OpenAI library not available, LLM-based element selection will be disabled")
            self.client = None
        elif not api_key:
            logger.warning("OPENAI_API_KEY not found, LLM-based element selection will be disabled")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)
    
    async def select_best_element(self, elements_with_info: List[Dict], user_prompt: str, page_info: Dict) -> Optional[Dict]:
        """
        Use LLM to decide which element is most relevant to click based on user's goal.
        
        Args:
            elements_with_info: List of element information dictionaries
            user_prompt: The user's search query or goal
            page_info: Information about the current page (title, url, etc.)
            
        Returns:
            Selected element information or None
        """
        if not elements_with_info:
            return None
            
        if not self.client:
            # Fallback to rule-based selection if no API key
            return self._rule_based_selection(elements_with_info, user_prompt)
        
        # Prepare the prompt with context
        prompt = f"""
        You are an AI assistant helping navigate a web page based on a user's search goal.
        
        USER'S GOAL: {user_prompt}
        
        CURRENT PAGE:
        Title: {page_info.get('title', 'Unknown')}
        URL: {page_info.get('url', 'Unknown')}
        
        CLICKABLE ELEMENTS ON PAGE:
        {json.dumps(elements_with_info, indent=2)}
        
        Based on the user's goal, select THE SINGLE MOST RELEVANT element to click on.
        Return ONLY a JSON object with format:
        {{
          "element_id": "ID of the selected element",
          "reason": "Brief explanation of why this element is the most relevant"
        }}
        
        If none of the elements look relevant, select one that leads to further exploration 
        or may provide navigation to the goal (like 'Next', 'More', 'View', 'Details', etc.).
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Find the element with the matching ID
            for element in elements_with_info:
                if element.get("id") == result.get("element_id"):
                    element["selection_reason"] = result.get("reason")
                    return element
            
            # If no exact match, return the first element as fallback
            if elements_with_info:
                elements_with_info[0]["selection_reason"] = "Fallback selection - no exact match found"
                return elements_with_info[0]
            return None
            
        except Exception as e:
            logger.warning(f"Error using LLM for element selection: {e}")
            return self._rule_based_selection(elements_with_info, user_prompt)
    
    def _rule_based_selection(self, elements_with_info: List[Dict], user_prompt: str) -> Optional[Dict]:
        """Fallback rule-based selection when LLM is not available"""
        if not elements_with_info:
            return None
            
        # Extract keywords from the prompt
        keywords = user_prompt.lower().split()
        best_match = None
        best_score = 0
        
        # Score each element based on text match with user prompt
        for element in elements_with_info:
            element_text = element.get("text", "").lower()
            element_type = element.get("element_type", "")
            
            # Calculate keyword match score
            score = sum(1 for keyword in keywords if keyword in element_text)
            
            # Boost score for navigation elements when needed
            if any(term in element_text for term in ["next", "continue", "more", "show", "view", "details"]):
                score += 0.5
                
            # Prioritize buttons and links
            if element_type in ["button", "link"]:
                score += 0.3
                
            if score > best_score:
                best_score = score
                best_match = element
        
        # If no good matches, prioritize navigation elements
        if not best_match or best_score == 0:
            for element in elements_with_info:
                text = element.get("text", "").lower()
                if any(term in text for term in ["next", "continue", "more", "show", "view", "details"]):
                    return element
            
            # Last resort: return the first element
            if elements_with_info:
                return elements_with_info[0]
        
        return best_match if best_match else (elements_with_info[0] if elements_with_info else None)

    async def generate_input_text(self, input_element_info: Dict, user_prompt: str, page_info: Dict) -> str:
        """
        Generate appropriate text to input in a form field based on context.
        
        Args:
            input_element_info: Information about the input element
            user_prompt: User's search query or goal
            page_info: Information about the current page
            
        Returns:
            Text to input into the form field
        """
        if not self.client:
            # Fallback if no API key
            return user_prompt[:50]  # Simple truncation
        
        # Prepare the prompt with context
        prompt = f"""
        You are an AI assistant helping fill in form fields on a website based on the user's goal.
        
        USER'S GOAL: {user_prompt}
        
        CURRENT PAGE:
        Title: {page_info.get('title', 'Unknown')}
        URL: {page_info.get('url', 'Unknown')}
        
        FORM FIELD DETAILS:
        Type: {input_element_info.get('type', 'text')}
        Placeholder: {input_element_info.get('placeholder', 'N/A')}
        Label: {input_element_info.get('label', 'N/A')}
        Name: {input_element_info.get('name', 'N/A')}
        
        Generate the most appropriate text to input in this field to help achieve the user's goal.
        Keep it concise and directly relevant.
        Return ONLY the text to be inputted, without quotes or explanations.
        Max length: 100 characters.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.3,
            )
            
            generated_text = response.choices[0].message.content.strip()
            # Make sure it's not too long
            return generated_text[:100]
            
        except Exception as e:
            logger.warning(f"Error using LLM for input generation: {e}")
            
            # Get the most relevant part of the user prompt
            input_type = input_element_info.get('type', '')
            placeholder = input_element_info.get('placeholder', '')
            
            # For search inputs, use the user prompt directly
            if input_type == 'search' or 'search' in placeholder.lower():
                return user_prompt[:50]
                
            # For email inputs, use a placeholder email
            if input_type == 'email':
                return "example@example.com"
                
            # Default fallback
            return user_prompt[:50]

async def perform_page_interactions(browser, user_prompt: str, max_time_seconds: int = 60) -> Dict[str, Any]:
    """
    Performs human-like interactive actions on the current page based on available UI elements.
    Thoroughly examines and interacts with all types of interactive elements including:
    - Input fields (text, search, email, etc.)
    - Dropdowns and select boxes
    - Radio buttons and checkboxes
    - Buttons and links
    - Tabs and accordions
    
    Uses LLM to intelligently decide which elements to interact with based on the user's goal.
    Will timeout after max_time_seconds to avoid spending too long on one page.
    
    Args:
        browser: The browser wrapper instance
        user_prompt: The user query to contextualize interactions
        max_time_seconds: Maximum time to spend on interactions before timing out
        
    Returns:
        dict: Information about actions performed
    """
    page = await browser.get_current_page()
    actions_performed = []
    
    # Initialize defaults for element counts
    clickable_count = 0
    form_inputs_count = 0
    dropdown_count = 0
    checkbox_radio_count = 0
    
    # Initialize the element selector with LLM capabilities
    element_selector = ElementSelector()
    
    # Get page information for context
    page_info = {
        "title": await page.title(),
        "url": page.url,
        "content_snippet": await extract_page_content_snippet(page)
    }
    
    logger.info(f"Exploring page: {page_info['title']} - {page_info['url']}")
    
    # Step 1: Thoroughly scan the page by scrolling multiple positions
    try:
        await thorough_page_scrolling(page)
        actions_performed.append("Thoroughly scrolled the page to discover all content")
        await asyncio.sleep(2)  # Wait for content to load
    except Exception as e:
        logger.warning(f"Error during page scanning: {e}")
    
    # Set up a time limit for page exploration
    start_time = asyncio.get_event_loop().time()
    timeout_reached = False
    
    # Function to check if we're exceeding time limit
    def is_timeout():
        elapsed_time = asyncio.get_event_loop().time() - start_time
        if elapsed_time > max_time_seconds:
            logger.warning(f"Page exploration timeout reached after {elapsed_time:.1f} seconds")
            return True
        return False
    
    # Step 2: Find and categorize ALL interactive elements
    try:
        # Get all interactive elements with details
        element_details = await get_interactive_elements_with_details(page)
        
        # Check timeout early to avoid unnecessary processing
        if is_timeout():
            logger.info("Timeout reached after element discovery, stopping further interaction")
            return {
                "actions_performed": actions_performed + ["Exploration timeout reached"],
                "elements_found": {
                    "clickable": clickable_count,
                    "form_inputs": form_inputs_count,
                    "dropdowns": dropdown_count,
                    "checkbox_radio": checkbox_radio_count
                },
                "timeout_reached": True
            }
        
        # Update counts of detected elements
        clickable_count = len(element_details["clickable"])
        form_inputs_count = len(element_details["inputs"])
        dropdown_count = len(element_details.get("dropdowns", []))
        checkbox_radio_count = len(element_details.get("checkbox_radio", []))
        
        logger.info(f"Found {clickable_count} clickable elements, {form_inputs_count} form inputs, " +
                   f"{dropdown_count} dropdowns, and {checkbox_radio_count} checkboxes/radio buttons")
        
        # Identify form groups for coherent interaction (related inputs that should be filled together)
        form_groups = await identify_form_groups(page, element_details)
        
        # Special handling: If we detect a search form with just one input and a submit button,
        # prioritize that interaction as it's likely the primary search functionality
        search_form = await find_search_form(page, element_details)
        if search_form:
            logger.info("Detected primary search form - prioritizing interaction")
            await interact_with_search_form(page, search_form, user_prompt, element_selector, page_info)
            actions_performed.append("Interacted with primary search form")
            # Return early since search form submission will navigate away
            return {
                "actions_performed": actions_performed,
                "elements_found": {
                    "clickable": clickable_count,
                    "form_inputs": form_inputs_count,
                    "dropdowns": dropdown_count,
                    "checkbox_radio": checkbox_radio_count
                }
            }
            
        # Step 3: Try different types of interactions based on what we find
        
        # 3.1: First, try interacting with form groups if found 
        if form_groups:
            for group in form_groups:
                # Check timeout before expensive operations
                if is_timeout():
                    actions_performed.append("Timeout reached during form group interaction")
                    timeout_reached = True
                    break
                    
                success = await interact_with_form_group(page, group, user_prompt, element_selector, page_info)
                if success:
                    actions_performed.append(f"Filled in form group: {group['description']}")
        
        # Check if timeout reached after form group interactions
        if timeout_reached:
            # Return early with timeout status
            return {
                "actions_performed": actions_performed,
                "elements_found": {
                    "clickable": clickable_count,
                    "form_inputs": form_inputs_count,
                    "dropdowns": dropdown_count,
                    "checkbox_radio": checkbox_radio_count
                },
                "timeout_reached": True
            }
            
        # 3.2: Handle individual dropdowns (select elements)
        if element_details.get("dropdowns"):
            for dropdown in element_details["dropdowns"]:
                # Check timeout before expensive operations
                if is_timeout():
                    actions_performed.append("Timeout reached during dropdown interaction")
                    timeout_reached = True
                    break
                    
                if await interact_with_dropdown(page, dropdown, user_prompt, element_selector, page_info):
                    actions_performed.append(f"Selected option from dropdown: {dropdown.get('label', 'Dropdown')}")
        
        # Check timeout again before next interaction type
        if timeout_reached:
            return {
                "actions_performed": actions_performed,
                "elements_found": {
                    "clickable": clickable_count,
                    "form_inputs": form_inputs_count,
                    "dropdowns": dropdown_count,
                    "checkbox_radio": checkbox_radio_count
                },
                "timeout_reached": True
            }
            
        # 3.3: Handle checkbox/radio button groups
        if element_details.get("checkbox_radio"):
            for element in element_details["checkbox_radio"]:
                # Check timeout before expensive operations
                if is_timeout():
                    actions_performed.append("Timeout reached during checkbox/radio interaction")
                    timeout_reached = True
                    break
                    
                if await interact_with_checkbox_radio(page, element, user_prompt, element_selector, page_info):
                    actions_performed.append(f"Toggled {element.get('type', 'checkbox/radio')}: {element.get('label', 'Option')}")
        
        # Check if timeout reached after checkbox/radio interactions
        if timeout_reached:
            return {
                "actions_performed": actions_performed,
                "elements_found": {
                    "clickable": clickable_count,
                    "form_inputs": form_inputs_count,
                    "dropdowns": dropdown_count,
                    "checkbox_radio": checkbox_radio_count
                },
                "timeout_reached": True
            }
            
        # 3.4: Handle individual input fields that weren't part of a form group
        standalone_inputs = [input for input in element_details["inputs"] 
                            if input.get("type") in ["text", "search", "email", "tel", "number"]]
        
        if standalone_inputs:
            # Check timeout before LLM operations
            if is_timeout():
                actions_performed.append("Timeout reached during input field processing")
                timeout_reached = True
                # Return early with timeout status
                return {
                    "actions_performed": actions_performed,
                    "elements_found": {
                        "clickable": clickable_count,
                        "form_inputs": form_inputs_count,
                        "dropdowns": dropdown_count,
                        "checkbox_radio": checkbox_radio_count
                    },
                    "timeout_reached": True
                }
                
            best_input = await element_selector.select_best_element(
                standalone_inputs, 
                user_prompt, 
                page_info
            )
            
            if best_input:
                try:
                    input_elem = await page.query_selector(best_input["selector"])
                    if input_elem:
                        # Generate appropriate input text using LLM
                        input_text = await element_selector.generate_input_text(
                            best_input,
                            user_prompt,
                            page_info
                        )
                        
                        await input_elem.fill(input_text)
                        logger.info(f"Filled input field ({best_input['type']}): '{input_text}'")
                        actions_performed.append(f"Filled in form input with: '{input_text}'")
                        
                        # Try to find and click a nearby submit button
                        submit_btn = await find_nearby_submit_button(page, input_elem)
                        if submit_btn:
                            await submit_btn.click()
                            logger.info("Clicked nearby submit button")
                            actions_performed.append("Submitted form by clicking submit button")
                            await asyncio.sleep(2)  # Wait for page to load
                            return {
                                "actions_performed": actions_performed,
                                "elements_found": {
                                    "clickable": clickable_count,
                                    "form_inputs": form_inputs_count,
                                    "dropdowns": dropdown_count,
                                    "checkbox_radio": checkbox_radio_count
                                }
                            }
                except Exception as e:
                    logger.warning(f"Error interacting with standalone input: {e}")
        
        # 3.5: Finally, if no successful form interactions, try clicking on the best clickable element
        if element_details["clickable"]:
            # Check timeout before final clickable element selection
            if is_timeout():
                actions_performed.append("Timeout reached during clickable element selection")
                # Return with timeout status
                return {
                    "actions_performed": actions_performed,
                    "elements_found": {
                        "clickable": clickable_count,
                        "form_inputs": form_inputs_count,
                        "dropdowns": dropdown_count,
                        "checkbox_radio": checkbox_radio_count
                    },
                    "timeout_reached": True
                }
                
            # Find the most relevant element to click
            best_element = await element_selector.select_best_element(
                element_details["clickable"], 
                user_prompt, 
                page_info
            )
            
            if best_element:
                try:
                    click_elem = await page.query_selector(best_element["selector"])
                    if click_elem and await click_elem.is_visible():
                        # For dropdown triggers, might need special handling
                        if best_element.get("element_type") in ["select", "combobox", "dropdown"]:
                            await click_elem.click()
                            logger.info(f"Clicked dropdown trigger: {best_element['text']}")
                            actions_performed.append(f"Opened dropdown: {best_element['text']}")
                            
                            # After opening dropdown, wait and try to select an option
                            await asyncio.sleep(1)
                            await select_dropdown_option(page, user_prompt)
                            actions_performed.append("Selected option from dropdown menu")
                        else:
                            # Standard click for other elements
                            await click_elem.click()
                            logger.info(f"Clicked element: {best_element['text']} (Reason: {best_element.get('selection_reason', 'N/A')})")
                            actions_performed.append(f"Clicked on: {best_element['text']}")
                            
                        await asyncio.sleep(2)  # Wait for any changes to take effect
                except Exception as e:
                    logger.warning(f"Error clicking element: {e}")
    except Exception as e:
        logger.error(f"Error during page interactions: {e}")
    
    # Return information about all actions performed
    result = {
        "actions_performed": actions_performed,
        "elements_found": {
            "clickable": clickable_count,
            "form_inputs": form_inputs_count,
            "dropdowns": dropdown_count,
            "checkbox_radio": checkbox_radio_count
        },
        "elements_interacted_with": [],  # Added to maintain API compatibility with MCP planner
        "timeout_reached": timeout_reached  # Flag indicating if a timeout occurred
    }
    
    return result

async def get_interactive_elements_with_details(page) -> Dict[str, List[Dict]]:
    """Get detailed information about all interactive elements on the page."""
    elements_info = {
        "clickable": [],
        "inputs": [],
        "dropdowns": [],
        "checkbox_radio": []
    }
    
    # Process clickable elements
    try:
        # Get all potentially clickable elements
        clickable_selectors = [
            'button', 
            'a[href]', 
            '[role="button"]', 
            '[onclick]', 
            'input[type="button"]', 
            'input[type="submit"]',
            '.btn',
            '[class*="button"]',
            '[class*="btn"]',
            '[tabindex="0"]',
            '[data-toggle]',
            '.accordion-header',
            '.card-header',
            '[aria-haspopup="true"]',
            '[role="tab"]'
        ]
        
        clickable_elements = await page.query_selector_all(', '.join(clickable_selectors))
        
        id_counter = 0
        for element in clickable_elements:
            id_counter += 1
            
            # Get element properties
            tag_name = await page.evaluate('el => el.tagName.toLowerCase()', element)
            text = await get_element_text(element)
            href = await element.get_attribute('href') if tag_name == 'a' else None
            role = await element.get_attribute('role') 
            element_id = await element.get_attribute('id')
            element_class = await element.get_attribute('class')
            
            # Get element selector for future reference
            selector = await generate_unique_selector(page, element)
            
            # Determine element type
            element_type = "link" if tag_name == 'a' else "button"
            if role:
                element_type = role
                
            # Only include visible elements with some text or identifiable attributes
            is_visible = await element.is_visible()
            if is_visible and (text or href or element_id or element_class):
                elements_info["clickable"].append({
                    "id": f"clickable_{id_counter}",
                    "text": text,
                    "element_type": element_type,
                    "href": href,
                    "tag": tag_name,
                    "selector": selector,
                    "visible": is_visible
                })
    except Exception as e:
        logger.warning(f"Error analyzing clickable elements: {e}")
    
    # Process regular form inputs (text, search, email, etc.)
    try:
        input_selectors = [
            'input[type="text"]', 
            'input[type="search"]', 
            'input[type="email"]',
            'input[type="password"]',
            'input[type="tel"]',
            'input[type="number"]',
            'input[type="date"]',
            'input[type="url"]',
            'textarea',
            '[contenteditable="true"]',
            '[role="textbox"]'
        ]
        
        input_elements = await page.query_selector_all(', '.join(input_selectors))
        
        id_counter = 0
        for element in input_elements:
            id_counter += 1
            
            # Get input properties
            input_type = await element.get_attribute('type') or 'text'
            placeholder = await element.get_attribute('placeholder') or ''
            name = await element.get_attribute('name') or ''
            element_id = await element.get_attribute('id') or ''
            
            # Try to find associated label
            label_text = await find_input_label(page, element, element_id)
            
            # Get element selector for future reference
            selector = await generate_unique_selector(page, element)
            
            # Only include visible inputs
            is_visible = await element.is_visible()
            if is_visible:
                elements_info["inputs"].append({
                    "id": f"input_{id_counter}",
                    "type": input_type,
                    "placeholder": placeholder,
                    "name": name,
                    "label": label_text,
                    "element_id": element_id,
                    "selector": selector,
                    "visible": is_visible
                })
    except Exception as e:
        logger.warning(f"Error analyzing form inputs: {e}")
    
    # Process dropdowns (select elements and custom dropdowns)
    try:
        dropdown_selectors = [
            'select',
            '[role="combobox"]',
            '[role="listbox"]',
            '.dropdown',
            '.dropdown-toggle',
            '[data-toggle="dropdown"]',
            '[aria-haspopup="listbox"]'
        ]
        
        dropdown_elements = await page.query_selector_all(', '.join(dropdown_selectors))
        
        id_counter = 0
        for element in dropdown_elements:
            id_counter += 1
            
            # Get dropdown properties
            tag_name = await page.evaluate('el => el.tagName.toLowerCase()', element)
            text = await get_element_text(element)
            element_id = await element.get_attribute('id') or ''
            
            # Try to find associated label
            label_text = await find_input_label(page, element, element_id)
            
            # Get element selector for future reference
            selector = await generate_unique_selector(page, element)
            
            # Determine dropdown type
            dropdown_type = "select" if tag_name == "select" else "dropdown"
            
            # Only include visible dropdowns
            is_visible = await element.is_visible()
            if is_visible:
                elements_info["dropdowns"].append({
                    "id": f"dropdown_{id_counter}",
                    "text": text,
                    "element_type": dropdown_type,
                    "label": label_text,
                    "element_id": element_id,
                    "selector": selector,
                    "visible": is_visible
                })
    except Exception as e:
        logger.warning(f"Error analyzing dropdowns: {e}")
    
    # Process checkboxes and radio buttons
    try:
        checkbox_radio_selectors = [
            'input[type="checkbox"]',
            'input[type="radio"]',
            '[role="checkbox"]',
            '[role="radio"]',
            '[role="switch"]'
        ]
        
        checkbox_radio_elements = await page.query_selector_all(', '.join(checkbox_radio_selectors))
        
        id_counter = 0
        for element in checkbox_radio_elements:
            id_counter += 1
            
            # Get properties
            input_type = await element.get_attribute('type') or await element.get_attribute('role') or 'checkbox'
            name = await element.get_attribute('name') or ''
            element_id = await element.get_attribute('id') or ''
            # Try to get checked state safely
            try:
                is_checked = await element.is_checked()
            except Exception:
                is_checked = False
            
            # Try to find associated label
            label_text = await find_input_label(page, element, element_id)
            
            # Get element selector for future reference
            selector = await generate_unique_selector(page, element)
            
            # Only include visible elements
            is_visible = await element.is_visible()
            if is_visible:
                elements_info["checkbox_radio"].append({
                    "id": f"check_radio_{id_counter}",
                    "type": input_type,
                    "name": name,
                    "label": label_text,
                    "element_id": element_id,
                    "selector": selector,
                    "visible": is_visible,
                    "checked": is_checked
                })
    except Exception as e:
        logger.warning(f"Error analyzing checkboxes/radio buttons: {e}")
        
    return elements_info

async def find_input_label(page, element, element_id=""):
    """Find the label text associated with an input element."""
    try:
        # Method 1: Check for explicit label with for attribute
        if element_id:
            label_element = await page.query_selector(f'label[for="{element_id}"]')
            if label_element:
                label_text = await label_element.text_content()
                if label_text:
                    return label_text.strip()
        
        # Method 2: Check if input is inside a label
        label_parent = await page.evaluate('''
            (element) => {
                const label = element.closest('label');
                return label ? true : false;
            }
        ''', element)
        
        if label_parent:
            label_text = await page.evaluate('''
                (element) => {
                    const label = element.closest('label');
                    return label ? label.textContent : '';
                }
            ''', element)
            
            if label_text:
                # Remove the text from the input itself from the label text
                input_text = await get_element_text(element)
                if input_text:
                    label_text = label_text.replace(input_text, '').strip()
                return label_text.strip()
        
        # Method 3: Check for aria-label attribute
        aria_label = await element.get_attribute('aria-label')
        if aria_label:
            return aria_label.strip()
        
        # Method 4: Check for nearby text that might be a label
        nearby_label = await page.evaluate('''
            (element) => {
                // Check previous siblings
                let sibling = element.previousElementSibling;
                if (sibling && sibling.textContent.trim()) {
                    return sibling.textContent;
                }
                
                // Check parent's first child if it's not our element
                let parent = element.parentElement;
                if (parent && parent.firstElementChild !== element && parent.firstElementChild) {
                    return parent.firstElementChild.textContent;
                }
                
                // Check for labels immediately before our element
                let possibleLabels = document.querySelectorAll('label, span, div, p');
                for (const label of possibleLabels) {
                    const rect1 = label.getBoundingClientRect();
                    const rect2 = element.getBoundingClientRect();
                    
                    // Label should be above or to the left of input
                    const isAbove = Math.abs(rect1.bottom - rect2.top) < 20;
                    const isLeftAligned = Math.abs(rect1.left - rect2.left) < 20;
                    const isToLeft = Math.abs(rect1.right - rect2.left) < 20;
                    
                    if ((isAbove || isLeftAligned || isToLeft) && label.textContent.trim()) {
                        return label.textContent;
                    }
                }
                
                return '';
            }
        ''', element)
        
        if nearby_label:
            return nearby_label.strip()
            
    except Exception as e:
        logger.warning(f"Error finding input label: {e}")
    
    return ""

async def generate_unique_selector(page, element):
    """Generate a unique CSS selector for an element."""
    try:
        # Try to use the element's ID if available
        element_id = await element.get_attribute('id')
        if element_id:
            # Escape special characters in the ID
            escaped_id = element_id.replace(':', '\\:').replace('.', '\\.')
            return f'#{escaped_id}'
        
        # Try to create a selector using an available attribute
        for attr in ['name', 'placeholder', 'role', 'type']:
            attr_value = await element.get_attribute(attr)
            if attr_value:
                tag_name = await page.evaluate('el => el.tagName.toLowerCase()', element)
                return f'{tag_name}[{attr}="{attr_value}"]'
        
        # Last resort: generate a complex selector based on tag and classes
        return await page.evaluate('''
            element => {
                function getPathTo(element) {
                    if (element.id)
                        return `//*[@id="${element.id}"]`;
                        
                    const parent = element.parentNode;
                    if (!parent)
                        return '';
                    
                    const siblings = Array.from(parent.children);
                    const tagSiblings = siblings.filter(sibling => 
                        sibling.tagName === element.tagName
                    );
                    
                    const idx = tagSiblings.indexOf(element) + 1;
                    
                    return `${getPathTo(parent)}/${element.tagName.toLowerCase()}[${idx}]`;
                }
                return getPathTo(element);
            }
        ''', element)
    except Exception as e:
        logger.warning(f"Error generating unique selector: {e}")
        return "body"  # Fallback selector

async def extract_page_content_snippet(page, max_length=1000):
    """Extract a snippet of the main content from the page for context."""
    try:
        # Try to get the main content
        content = await page.evaluate('''
            () => {
                // Try to find main content area with common selectors
                const selectors = [
                    'main', 
                    '[role="main"]', 
                    '#main-content', 
                    '.main-content', 
                    'article', 
                    '.content', 
                    '#content'
                ];
                
                for (const selector of selectors) {
                    const element = document.querySelector(selector);
                    if (element) {
                        return element.textContent;
                    }
                }
                
                // Fallback to body content
                return document.body.textContent;
            }
        ''')
        
        if content:
            # Clean up the content (JavaScript methods won't work in Python)
            content = ' '.join(content.split())
            # Truncate if needed
            if len(content) > max_length:
                return content[:max_length] + "..."
            return content
    except Exception as e:
        logger.warning(f"Error extracting page content: {e}")
    
    return ""

async def thorough_page_scrolling(page):
    """Scroll through the page thoroughly to load all dynamic content."""
    try:
        # Get page height
        height = await page.evaluate('() => document.body.scrollHeight')
        
        # Scroll in increments
        step = height / 5  # Divide into 5 sections
        
        for i in range(6):  # 0%, 20%, 40%, 60%, 80%, 100%
            position = i * step
            await page.evaluate(f'''
                () => {{
                    window.scrollTo({{
                        top: {position},
                        behavior: 'smooth'
                    }});
                }}
            ''')
            await asyncio.sleep(0.5)  # Wait between scrolls
            
        # Final scroll back to top
        await page.evaluate('''
            () => {
                window.scrollTo({
                    top: 0,
                    behavior: 'smooth'
                });
            }
        ''')
        await asyncio.sleep(0.5)
    except Exception as e:
        logger.warning(f"Error during thorough scrolling: {e}")

async def identify_form_groups(page, element_details):
    """Identify logical form groups (inputs that should be filled together)."""
    form_groups = []
    
    try:
        # Find all form elements
        forms = await page.query_selector_all('form')
        
        for i, form in enumerate(forms):
            # Get all inputs within this form
            form_inputs = []
            
            # Find selector for the form
            form_selector = await generate_unique_selector(page, form)
            
            # Collect all inputs that belong to this form
            for input_elem in element_details["inputs"]:
                input_selector = input_elem["selector"]
                belongs_to_form = await page.evaluate(f'''
                    (selector, formSelector) => {{
                        const input = document.querySelector(selector);
                        const form = document.querySelector(formSelector);
                        return input && form && form.contains(input);
                    }}
                ''', input_selector, form_selector)
                
                if belongs_to_form:
                    form_inputs.append(input_elem)
            
            # If we found multiple inputs in this form, consider it a form group
            if len(form_inputs) > 1:
                # Try to get form description (e.g. from legend, title attribute, etc.)
                description = await get_form_description(page, form) or f"Form {i+1}"
                
                form_groups.append({
                    "id": f"form_group_{i}",
                    "inputs": form_inputs,
                    "description": description,
                    "selector": form_selector
                })
    except Exception as e:
        logger.warning(f"Error identifying form groups: {e}")
    
    return form_groups

async def get_form_description(page, form_elem):
    """Try to get a description for a form from various attributes."""
    try:
        # Check for legend elements
        legend = await form_elem.query_selector('legend')
        if legend:
            legend_text = await legend.text_content()
            if legend_text:
                return legend_text.strip()
        
        # Check for form title attribute
        title = await form_elem.get_attribute('title')
        if title:
            return title
        
        # Check for aria-label
        aria_label = await form_elem.get_attribute('aria-label')
        if aria_label:
            return aria_label
        
        # Check for nearby headings
        heading = await form_elem.query_selector('h1, h2, h3, h4, h5, h6')
        if heading:
            heading_text = await heading.text_content()
            if heading_text:
                return heading_text.strip()
                
        # Check for label elements
        labels = await form_elem.query_selector_all('label')
        if labels and len(labels) > 0:
            label_texts = []
            for label in labels[:3]:  # Get first 3 labels max
                text = await label.text_content()
                if text:
                    label_texts.append(text.strip())
            if label_texts:
                return ", ".join(label_texts)
    except Exception as e:
        logger.warning(f"Error getting form description: {e}")
    
    return None

async def find_search_form(page, element_details):
    """Identify if the page has a primary search form."""
    try:
        # Look for search inputs
        search_inputs = [input for input in element_details["inputs"] 
                        if (input.get("type") == "search" or 
                            "search" in input.get("name", "").lower() or 
                            "search" in input.get("placeholder", "").lower() or
                            "search" in input.get("label", "").lower())]
        
        if search_inputs:
            # For each search input, check if there's a submit button nearby
            for search_input in search_inputs:
                input_elem = await page.query_selector(search_input["selector"])
                if not input_elem:
                    continue
                    
                submit_btn = await find_nearby_submit_button(page, input_elem)
                if submit_btn:
                    return {
                        "input": search_input,
                        "submit_button": await generate_unique_selector(page, submit_btn)
                    }
                    
            # If no submit button found but we have a search input, return just the input
            return {"input": search_inputs[0]}
    except Exception as e:
        logger.warning(f"Error finding search form: {e}")
    
    return None

async def find_nearby_submit_button(page, input_elem):
    """Find a submit button that's likely associated with the given input element."""
    try:
        # First check if input is in a form, and find the form's submit button
        form = await page.evaluate('''
            (element) => {
                const form = element.closest('form');
                return form ? true : false;
            }
        ''', input_elem)
        
        if form:
            # Find submit button within the same form
            submit_btn = await page.evaluate('''
                (element) => {
                    const form = element.closest('form');
                    if (!form) return null;
                    
                    // Look for submit buttons or inputs
                    const submitElement = form.querySelector('button[type="submit"], input[type="submit"], button:not([type]), [role="button"]');
                    
                    // If no explicit submit button, look for buttons with submit-like text
                    if (!submitElement) {
                        const buttons = Array.from(form.querySelectorAll('button, [role="button"], a.btn, .button, input[type="button"]'));
                        for (const btn of buttons) {
                            const text = btn.textContent.toLowerCase();
                            if (text.includes('search') || text.includes('submit') || text.includes('go') || 
                                text.includes('find') || text.includes('send') || text.includes('next')) {
                                return btn;
                            }
                        }
                    }
                    
                    return submitElement;
                }
            ''', input_elem)
            
            if submit_btn:
                return submit_btn
        
        # If no form or no submit button in form, look for nearby buttons
        nearby_button = await page.evaluate('''
            (element) => {
                // Look for buttons near the input (siblings or parent's children)
                let parent = element.parentElement;
                if (!parent) return null;
                
                // First check siblings
                let siblings = Array.from(parent.children);
                for (const sibling of siblings) {
                    if (sibling === element) continue;
                    
                    if (sibling.tagName === 'BUTTON' || 
                        sibling.getAttribute('role') === 'button' || 
                        sibling.tagName === 'INPUT' && sibling.type === 'submit' ||
                        sibling.classList.contains('btn') || 
                        sibling.classList.contains('button')) {
                        return sibling;
                    }
                }
                
                // Check parent's parent children (cousins)
                let grandparent = parent.parentElement;
                if (grandparent) {
                    let cousins = Array.from(grandparent.children);
                    for (const cousin of cousins) {
                        if (cousin === parent) continue;
                        
                        const button = cousin.querySelector('button, [role="button"], input[type="submit"], .btn, .button');
                        if (button) return button;
                    }
                }
                
                return null;
            }
        ''', input_elem)
        
        return nearby_button
    except Exception as e:
        logger.warning(f"Error finding nearby submit button: {e}")
        return None

async def interact_with_search_form(page, search_form, user_prompt, element_selector, page_info):
    """Interact with a search form by filling the input and clicking submit."""
    try:
        # Get the input element
        input_elem_info = search_form["input"]
        input_elem = await page.query_selector(input_elem_info["selector"])
        
        if not input_elem:
            logger.warning("Search input element not found")
            return False
            
        # Generate appropriate search text using LLM
        search_text = await element_selector.generate_input_text(
            input_elem_info,
            user_prompt,
            page_info
        )
        
        # Fill in the search text
        await input_elem.fill(search_text)
        logger.info(f"Filled search input with: '{search_text}'")
        
        # If we have a submit button, click it
        if "submit_button" in search_form:
            submit_btn = await page.query_selector(search_form["submit_button"])
            if submit_btn:
                await submit_btn.click()
                logger.info("Clicked search submit button")
                await asyncio.sleep(2)  # Wait for search results
                return True
                
        # Otherwise, press Enter to submit
        await input_elem.press("Enter")
        logger.info("Pressed Enter to submit search")
        await asyncio.sleep(2)  # Wait for search results
        return True
        
    except Exception as e:
        logger.warning(f"Error interacting with search form: {e}")
        return False

async def interact_with_form_group(page, form_group, user_prompt, element_selector, page_info):
    """Fill in all fields in a form group intelligently."""
    try:
        inputs_filled = 0
        
        # For each input in the form
        for input_info in form_group["inputs"]:
            input_elem = await page.query_selector(input_info["selector"])
            if not input_elem or not await input_elem.is_visible():
                continue
                
            input_type = input_info.get("type", "text")
            
            # Handle different input types
            if input_type in ["text", "search", "email", "tel", "number", "password"]:
                # Generate appropriate text
                input_text = await element_selector.generate_input_text(
                    input_info,
                    user_prompt,
                    page_info
                )
                
                await input_elem.fill(input_text)
                logger.info(f"Filled form input ({input_type}): '{input_text}'")
                inputs_filled += 1
                
            elif input_type == "checkbox" or input_type == "radio":
                # Decide whether to check this box/radio based on relevance to user goal
                should_check = await should_toggle_checkbox(input_info, user_prompt, element_selector, page_info)
                
                if should_check:
                    await input_elem.check()
                    logger.info(f"Checked {input_type}: {input_info.get('label', input_info.get('id', 'Unknown'))}")
                    inputs_filled += 1
                    
            elif input_type == "file":
                # File uploads are complex, just log for now
                logger.info(f"Found file input: {input_info.get('id', 'Unknown')} (not automatically handling file uploads)")
                
            # Brief pause between inputs to simulate human behavior
            await asyncio.sleep(0.5)
            
        # After filling inputs, try to find and click a submit button
        form_elem = await page.query_selector(form_group["selector"])
        if form_elem:
            submit_btns = await form_elem.query_selector_all('button[type="submit"], input[type="submit"], button:not([type])')
            
            if submit_btns and len(submit_btns) > 0:
                await submit_btns[0].click()
                logger.info(f"Submitted form: {form_group['description']}")
                await asyncio.sleep(2)  # Wait for form submission
                return True
                
        return inputs_filled > 0
        
    except Exception as e:
        logger.warning(f"Error interacting with form group: {e}")
        return False

async def should_toggle_checkbox(checkbox_info, user_prompt, element_selector, page_info):
    """Decide whether a checkbox or radio button should be checked based on user's goal."""
    # If it has the LLM client, ask it
    if element_selector.client:
        try:
            prompt = f"""
            You are helping decide whether to select a checkbox or radio button on a web page 
            based on the user's goal.
            
            USER'S GOAL: {user_prompt}
            
            CURRENT PAGE:
            Title: {page_info.get('title', 'Unknown')}
            URL: {page_info.get('url', 'Unknown')}
            
            CHECKBOX/RADIO BUTTON:
            Label: {checkbox_info.get('label', 'N/A')}
            Type: {checkbox_info.get('type', 'checkbox')}
            Name: {checkbox_info.get('name', 'N/A')}
            
            Should this checkbox/radio button be checked based on the user's goal?
            Return ONLY 'yes' or 'no'.
            """
            
            response = element_selector.client.chat.completions.create(
                model=element_selector.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.3,
            )
            
            decision = response.choices[0].message.content.strip().lower()
            return decision == "yes"
            
        except Exception as e:
            logger.warning(f"Error using LLM for checkbox decision: {e}")
    
    # Fallback: scoring system for checkbox decisions
    label = checkbox_info.get('label', '').lower()
    if not label:
        logger.info("No label found for checkbox, defaulting to unchecked")
        return False
        
    logger.info(f"Evaluating checkbox/radio: '{label}'")
    
    # Initialize score
    score = 0
    
    # Positive indicators that suggest checking the box
    positive_terms = ['agree', 'accept', 'yes', 'subscribe', 'sign up', 'enable', 'activate', 
                      'show', 'display', 'view', 'include', 'more', 'details']
    
    # Negative indicators that suggest not checking the box
    negative_terms = ['disagree', 'decline', 'no', 'unsubscribe', 'opt out', 'disable', 'deactivate',
                     'hide', 'remove', 'exclude', 'less', 'don\'t', 'do not']
    
    # Market-related terms that we generally avoid unless specifically requested
    marketing_terms = ['newsletter', 'email', 'updates', 'promotions', 'marketing', 
                       'offers', 'notifications', 'alerts']
    
    # Check if any user keywords are in the label
    user_keywords = user_prompt.lower().split()
    keyword_matches = [keyword for keyword in user_keywords if keyword in label]
    
    # If there are keyword matches, strongly favor checking
    if keyword_matches:
        score += len(keyword_matches) * 5
        logger.info(f"  - Contains {len(keyword_matches)} user keywords: +{len(keyword_matches) * 5}")
    
    # Check for positive terms
    positive_matches = [term for term in positive_terms if term in label]
    if positive_matches:
        score += len(positive_matches) * 2
        logger.info(f"  - Contains {len(positive_matches)} positive terms: +{len(positive_matches) * 2}")
    
    # Check for negative terms
    negative_matches = [term for term in negative_terms if term in label]
    if negative_matches:
        score -= len(negative_matches) * 3
        logger.info(f"  - Contains {len(negative_matches)} negative terms: -{len(negative_matches) * 3}")
    
    # Terms and conditions, privacy policy, etc. usually need to be checked
    if any(term in label for term in ['terms', 'conditions', 'privacy', 'policy', 'agree', 'consent', 'required']):
        score += 10
        logger.info(f"  - Contains required terms/privacy acceptance: +10")
    
    # Marketing terms - only check if specifically requested
    marketing_matches = [term for term in marketing_terms if term in label]
    if marketing_matches and not any(term in user_prompt.lower() for term in marketing_terms):
        score -= len(marketing_matches) * 2
        logger.info(f"  - Contains {len(marketing_matches)} marketing terms not in user query: -{len(marketing_matches) * 2}")
    
    # If this is a radio button, we generally want to select it if it matches keywords
    if checkbox_info.get('type', '') == 'radio' and keyword_matches:
        score += 3
        logger.info(f"  - Is a radio button with matching keywords: +3")
    
    # If "required" is mentioned anywhere, we need to check it
    if "required" in label or checkbox_info.get('name', '').lower().find('required') >= 0:
        score += 7
        logger.info(f"  - Marked as required: +7")
    
    # Make the decision
    should_check = score > 0
    logger.info(f"  - Final score: {score}, Decision: {'CHECK' if should_check else 'UNCHECK'}")
    
    return should_check

async def interact_with_dropdown(page, dropdown_info, user_prompt, element_selector, page_info):
    """Select an appropriate option from a dropdown menu based on user goal."""
    try:
        dropdown = await page.query_selector(dropdown_info["selector"])
        if not dropdown or not await dropdown.is_visible():
            return False
            
        # Get all available options
        options = await get_dropdown_options(page, dropdown)
        if not options or len(options) == 0:
            return False
            
        # Use LLM to select the best option if available
        selected_option = None
        
        if element_selector.client:
            try:
                prompt = f"""
                You are helping select the most appropriate option from a dropdown menu
                based on the user's goal.
                
                USER'S GOAL: {user_prompt}
                
                CURRENT PAGE:
                Title: {page_info.get('title', 'Unknown')}
                URL: {page_info.get('url', 'Unknown')}
                
                DROPDOWN:
                Label: {dropdown_info.get('label', 'N/A')}
                
                AVAILABLE OPTIONS:
                {", ".join(f"'{option}'" for option in options)}
                
                Select the SINGLE most appropriate option based on the user's goal.
                Return ONLY the exact text of the option to select.
                If none seem appropriate, select a default or neutral option.
                """
                
                response = element_selector.client.chat.completions.create(
                    model=element_selector.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=50,
                    temperature=0.3,
                )
                
                selected_option = response.choices[0].message.content.strip()
                
                # Make sure the selected option actually exists
                if selected_option not in options:
                    # Try to find a close match
                    for option in options:
                        if selected_option.lower() in option.lower():
                            selected_option = option
                            break
                    else:
                        selected_option = None  # No match found
                        
            except Exception as e:
                logger.warning(f"Error using LLM for dropdown selection: {e}")
        
        # Fallback: rule-based selection
        if not selected_option:
            selected_option = select_best_dropdown_option(options, user_prompt)
        
        # Select the option
        if selected_option:
            # Different approaches for selecting might be needed depending on the dropdown implementation
            success = await try_select_dropdown_option(page, dropdown, selected_option)
            
            if success:
                logger.info(f"Selected dropdown option: '{selected_option}'")
                return True
                
        return False
        
    except Exception as e:
        logger.warning(f"Error interacting with dropdown: {e}")
        return False

async def get_dropdown_options(page, dropdown):
    """Get all options from a dropdown element."""
    try:
        # For standard select elements
        if await page.evaluate('element => element.tagName.toLowerCase() === "select"', dropdown):
            options = await page.evaluate('''
                element => {
                    return Array.from(element.options).map(option => option.text.trim()).filter(text => text);
                }
            ''', dropdown)
            return options
            
        # For custom dropdowns, try to find option elements
        options = await page.evaluate('''
            element => {
                // Click to open the dropdown if needed
                if (!element.getAttribute('open') && !element.classList.contains('show') && 
                    !element.classList.contains('active') && !element.getAttribute('aria-expanded') === 'true') {
                    element.click();
                }
                
                // Look for options with different common patterns
                const optionElements = element.querySelectorAll('option, [role="option"], .dropdown-item, .select-option, li');
                return Array.from(optionElements).map(opt => opt.textContent.trim()).filter(text => text);
            }
        ''', dropdown)
        
        return options
        
    except Exception as e:
        logger.warning(f"Error getting dropdown options: {e}")
        return []

def select_best_dropdown_option(options, user_prompt):
    """Rule-based selection of the best dropdown option based on user prompt."""
    if not options:
        return None
        
    # Extract keywords from the prompt
    keywords = user_prompt.lower().split()
    
    # Score each option based on keyword matches
    best_option = None
    best_score = -1
    
    for option in options:
        option_lower = option.lower()
        
        # Calculate a score based on keyword matches
        score = sum(1 for keyword in keywords if keyword in option_lower)
        
        # Prefer options with exact matches
        if score > best_score:
            best_score = score
            best_option = option
    
    # If no good match found, apply sensible defaults
    if best_score == 0:
        # For country selections, prefer common options
        if any(country in str(options).lower() for country in ["united states", "canada", "uk", "australia"]):
            for default_country in ["United States", "US", "USA", "U.S.A.", "U.S."]:
                if default_country in options:
                    return default_country
        
        # For other cases, avoid first option if it's a placeholder
        first_option = options[0].lower()
        if "select" in first_option or "choose" in first_option or "please" in first_option:
            return options[1] if len(options) > 1 else options[0]
            
        # Default to first option
        return options[0]
    
    return best_option

async def try_select_dropdown_option(page, dropdown, option_text):
    """Try different methods to select an option from a dropdown."""
    try:
        # Method 1: Standard select element
        tag_name = await page.evaluate('element => element.tagName.toLowerCase()', dropdown)
        
        if tag_name == "select":
            await page.select_option(
                await generate_unique_selector(page, dropdown),
                {"label": option_text}
            )
            return True
            
        # Method 2: Click the dropdown to open it
        await dropdown.click()
        await asyncio.sleep(0.5)  # Wait for animation
        
        # Method 3: Find and click the specific option
        option_found = await page.evaluate('''
            (dropdownElement, optionText) => {
                // First try to find the option directly
                const options = dropdownElement.querySelectorAll('option, [role="option"], .dropdown-item, .select-option, li');
                
                for (const option of options) {
                    if (option.textContent.trim() === optionText) {
                        option.click();
                        return true;
                    }
                }
                
                // If not found, check the entire document (for dropdowns that create elements in a portal)
                const allOptions = document.querySelectorAll('option, [role="option"], .dropdown-item, .select-option, li');
                
                for (const option of allOptions) {
                    if (option.textContent.trim() === optionText) {
                        option.click();
                        return true;
                    }
                }
                
                return false;
            }
        ''', dropdown, option_text)
        
        return option_found
        
    except Exception as e:
        logger.warning(f"Error selecting dropdown option: {e}")
        return False

async def select_dropdown_option(page, user_prompt):
    """Select an appropriate option from an opened dropdown menu."""
    try:
        # Look for visible dropdown options that appeared after clicking
        # Use a more comprehensive selector to catch more dropdown option types
        option_elements = await page.query_selector_all('option:visible, [role="option"]:visible, .dropdown-item:visible, .select-option:visible, li:visible, .menu-item:visible, .autocomplete-option:visible')
        
        if not option_elements or len(option_elements) == 0:
            logger.info("No visible dropdown options found")
            return False
            
        logger.info(f"Found {len(option_elements)} potential dropdown options")
            
        # Get text of all options
        options = []
        for option in option_elements:
            text = await get_element_text(option)
            if text:
                options.append({"text": text, "element": option})
                
        if not options:
            return False
            
        # Filter out placeholder options
        non_placeholder_options = []
        placeholder_terms = ["select", "choose", "--", "pick", "please"]
        
        for option in options:
            text = option["text"].lower()
            is_placeholder = any(term in text for term in placeholder_terms)
            
            if not is_placeholder and len(text.strip()) > 1:  # Skip very short or empty options
                non_placeholder_options.append(option)
        
        # If we found non-placeholder options, use those
        option_list = non_placeholder_options if non_placeholder_options else options
        logger.info(f"Found {len(option_list)} meaningful dropdown options after filtering")
        
        # Do keyword matching to select best option
        keywords = user_prompt.lower().split()
        best_match = None
        best_score = 0
        
        for option in option_list:
            text = option["text"].lower()
            # Basic keyword matching
            score = sum(2 for keyword in keywords if keyword in text)
            
            # Boost score for options that look like they contain relevant information
            if any(term in text for term in ["yes", "show", "details", "more", "view", "info"]):
                score += 2
                
            # Avoid "No" options unless they explicitly match keywords
            if "no" in text and not any(keyword in ["no", "not", "don't"] for keyword in keywords):
                score -= 1
                
            # Prefer options with more text (likely more content)
            score += min(2, len(text) / 20)  # Add up to 2 points for longer text
            
            logger.info(f"Option '{text}' score: {score}")
            
            if score > best_score:
                best_score = score
                best_match = option
                
        # If no good match, use the option with the most text (likely most informative)
        if best_score == 0 and option_list:
            sorted_options = sorted(option_list, key=lambda x: len(x["text"]), reverse=True)
            best_match = sorted_options[0]
            logger.info(f"No keyword match, using longest option: {best_match['text']}")
            
        if best_match:
            await best_match["element"].click()
            logger.info(f"Selected dropdown option: {best_match['text']}")
            return True
            
        return False
        
    except Exception as e:
        logger.warning(f"Error selecting from open dropdown: {e}")
        return False

async def interact_with_checkbox_radio(page, element_info, user_prompt, element_selector, page_info):
    """Toggle a checkbox or radio button based on user goal."""
    try:
        element = await page.query_selector(element_info["selector"])
        if not element or not await element.is_visible():
            return False
            
        # Decide whether to check this box/radio
        should_check = await should_toggle_checkbox(element_info, user_prompt, element_selector, page_info)
        
        # Get current state
        is_checked = await element.is_checked()
        
        # Only take action if needed
        if should_check != is_checked:
            if should_check:
                await element.check()
                logger.info(f"Checked {element_info.get('type', 'checkbox/radio')}: {element_info.get('label', 'Unknown')}")
            else:
                await element.uncheck()
                logger.info(f"Unchecked {element_info.get('type', 'checkbox/radio')}: {element_info.get('label', 'Unknown')}")
                
            return True
            
        return False
        
    except Exception as e:
        logger.warning(f"Error interacting with checkbox/radio: {e}")
        return False

async def get_element_text(element):
    """Get the text of an element with fallbacks to various attributes."""
    try:
        text = await element.text_content()
        if text:
            return text.strip()
        
        # If no direct text, try to get other attributes
        for attr in ["value", "placeholder", "title", "aria-label", "alt"]:
            attr_value = await element.get_attribute(attr)
            if attr_value:
                return attr_value.strip()
        
        return ""
    except Exception:
        return ""
