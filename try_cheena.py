import logging
import asyncio
import json
import os
import re
from typing import List, Dict, Any, Optional, Tuple

from playwright.async_api import async_playwright, Page, BrowserContext, ElementHandle, Locator
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.messages import SystemMessage, HumanMessage
# Assuming you have a Langchain LLM initialized, e.g., from OpenAI, Anthropic, or Google
from langchain_openai import ChatOpenAI # Or other provider
from dotenv import load_dotenv

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables if using .env file (for API keys)
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set.")

# Initialize your LLM (replace with your actual LLM setup)
# Example using OpenAI (make sure you have the library installed: pip install langchain-openai)
llm = ChatOpenAI(model="gpt-4o", temperature=0.0, api_key=OPENAI_API_KEY)
# Replace this llm placeholder with your actual Langchain LLM instance
llm: Optional[BaseLanguageModel] = None # MUST BE REPLACED

# --- Constants ---
MAX_BROWSE_STEPS = 10  # Max interactions per page
MAX_SEARCH_RESULTS = 3 # Max search results to try
INTERACTIVE_ELEMENT_SELECTOR = 'a, button, input:not([type="hidden"]), textarea, select, [role="button"], [role="link"], [role="menuitem"]'
# Unique attribute to add to elements for the LLM to reference
BWE_ID_ATTRIBUTE = "data-bwe-id"

# --- User's Existing Functions (Adapted Slightly) ---

async def refine_search_query(llm: BaseLanguageModel, original_query: str) -> str:
    """
    Uses LLM to refine the raw user query into an optimized search query for Google.
    Returns the refined query as plain text.
    """
    if not llm:
        logger.warning("LLM not initialized. Using original query.")
        return original_query

    messages = [
        SystemMessage(content=(
            "You are an expert search query refiner. Your job is to transform a user's raw question "
            "into a concise and targeted search query that will yield highly relevant results on Google. "
            "If the input includes any output format instructions (like JSON, CSV, etc.), ignore them. "
            "Focus on the core information needed. "
            "Return only the refined search query in plain text with no additional commentary or quotes."
        )),
        HumanMessage(content=f"Original query: {original_query}")
    ]

    try:
        response = await llm.ainvoke(input=messages)
        refined_query = response.content.strip().strip('"')
        logger.info(f"Refined search query: {refined_query}")
        return refined_query
    except Exception as e:
        logger.error(f"Error refining search query: {e}")
        return original_query # Fallback to original

async def search_google(query: str, context: BrowserContext) -> list[dict]:
    """
    Perform a Google search and return the top search results.
    Uses a new page within the existing browser context.
    """
    page = await context.new_page()
    results = []
    try:
        # Use a user agent to look less like a bot
        await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})
        search_url = f'https://www.google.com/search?q={query}' # Simpler search URL often works better
        logger.info(f"Navigating to Google Search: {search_url}")
        await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)

        # Wait for search results container to ensure results are loaded
        await page.wait_for_selector('#search', state='visible', timeout=20000)

        # More robust selector for search results
        results = await page.evaluate('''() => {
            const items = [];
            document.querySelectorAll('div.g').forEach(el => {
                const link = el.querySelector('a');
                const h3 = el.querySelector('h3');
                const snippet_element = el.querySelector('div[data-sncf="1"]'); // Common snippet container

                if (link && h3 && link.href && !link.href.startsWith('https://www.google.com/search?')) { // Exclude 'People also ask' etc inside results
                     // Ensure href is absolute
                    const url = new URL(link.href, document.baseURI).href;
                     items.push({
                        title: h3.innerText,
                        url: url,
                        snippet: snippet_element ? snippet_element.innerText : ''
                    });
                }
            });
            // Prioritize results with snippets, then take top N
            items.sort((a, b) => (b.snippet.length > 0) - (a.snippet.length > 0));
            return items.slice(0, 5); // Get top 5 initially
        }''')

        logger.info(f'Searched for "{query}" on Google. Found {len(results)} potential results.')

    except Exception as e:
        logger.error(f"Error during Google search for '{query}': {e}")
        try:
             # Save screenshot for debugging if search fails
            await page.screenshot(path=f"error_Google Search_{re.sub(r'[^a-zA-Z0-9]+', '_', query)}.png")
            logger.info("Saved error screenshot.")
        except Exception as screenshot_err:
             logger.error(f"Could not save error screenshot: {screenshot_err}")

    finally:
        await page.close() # Close the search page

    # Filter out low-quality results (e.g., youtube, empty titles/urls)
    filtered_results = [
        r for r in results
        if r.get('url') and r.get('title') and 'youtube.com' not in r['url']
    ]
    return filtered_results[:MAX_SEARCH_RESULTS]


# --- New Agent Functions ---

async def simplify_page_for_llm(page: Page) -> Tuple[str, str]:
    """
    Gets the current page URL and a simplified representation of the page content,
    assigning unique IDs to interactive elements.

    Returns:
        Tuple[str, str]: (current_url, simplified_content_string)
    """
    current_url = page.url
    logger.info(f"Simplifying page content for URL: {current_url}")

    # Inject script to assign unique IDs to interactive elements
    try:
        await page.evaluate(f'''
            (async () => {{
                const selector = `{INTERACTIVE_ELEMENT_SELECTOR}`;
                const attr = `{BWE_ID_ATTRIBUTE}`;
                let counter = 0;
                // Remove old IDs first
                document.querySelectorAll(`[{attr}]`).forEach(el => el.removeAttribute(attr));
                // Add new IDs
                document.querySelectorAll(selector).forEach(el => {{
                    if (!el.hasAttribute(attr)) {{
                       el.setAttribute(attr, counter.toString());
                       counter++;
                    }}
                }});
            }})();
        ''')
    except Exception as e:
        logger.error(f"Error injecting ID assignment script: {e}")
        # Proceed anyway, but element referencing might fail

    # Get text content and details of interactive elements
    try:
        page_content = await page.evaluate(f'''
            (() => {{
                const interactiveElements = [];
                const attr = `{BWE_ID_ATTRIBUTE}`;
                document.querySelectorAll(`[{attr}]`).forEach(el => {{
                    const id = el.getAttribute(attr);
                    const tagName = el.tagName.toLowerCase();
                    let text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().substring(0, 100); // Limit text length
                    let elementType = tagName;
                    if (tagName === 'a') elementType = 'Link';
                    else if (tagName === 'button' || el.getAttribute('role') === 'button') elementType = 'Button';
                    else if (tagName === 'input') {{
                         elementType = `Input (type=${el.type || 'text'})`;
                         if (el.type === 'radio' || el.type === 'checkbox') {{
                            text += el.checked ? ' [checked]' : '';
                         }}
                    }}
                    else if (tagName === 'textarea') elementType = 'Textarea';
                    else if (tagName === 'select') elementType = 'Select';

                    // Clean up text slightly
                    text = text.replace(/\s+/g, ' ').trim();

                    if (text || elementType !== tagName) {{ // Only include if we have some text or a specific type
                         interactiveElements.push({{ id: id, type: elementType, text: text }});
                    }}
                }});

                // Try to get main content text, excluding scripts/styles/nav/footer if possible
                let mainText = '';
                const mainEl = document.querySelector('main') || document.body;
                 if (mainEl) {{
                     // Clone node to avoid modifying the original DOM for text extraction
                     const clone = mainEl.cloneNode(true);
                     // Remove elements likely not part of main content
                     clone.querySelectorAll('script, style, nav, footer, header, aside').forEach(el => el.remove());
                     mainText = clone.innerText;
                 }}

                // Limit main text length
                mainText = mainText.replace(/\s+/g, ' ').trim().substring(0, 2000); // Limit overall text length

                return {{
                    interactive: interactiveElements,
                    mainText: mainText
                }};
            }})();
        ''')

        # Format the simplified content for the LLM
        simplified_output = f"Current URL: {current_url}\n\n"
        simplified_output += "Main Page Text Snippet:\n---\n"
        simplified_output += page_content.get('mainText', 'Could not extract main text.')
        simplified_output += "\n---\n\nInteractive Elements:\n"

        if page_content.get('interactive'):
            for el in page_content['interactive']:
                simplified_output += f"- {el['type']} (id={el['id']}): \"{el['text']}\"\n"
        else:
            simplified_output += "No interactive elements found or identified.\n"

        return current_url, simplified_output

    except Exception as e:
        logger.error(f"Error simplifying page content: {e}")
        return current_url, f"Error extracting content: {e}. Current URL: {current_url}"


async def ask_llm_for_action(llm: BaseLanguageModel, goal: str, page_representation: str, history: List[str]) -> Optional[Dict[str, Any]]:
    """
    Asks the LLM to decide the next action based on the goal and page state.
    """
    if not llm:
        logger.error("LLM not provided for action decision.")
        return {"action": "fail", "reason": "LLM not available."}

    action_descriptions = """
Available Actions:
1.  `CLICK(id="element_id", reason="why")`: Click an interactive element (Link, Button). Use the id provided.
2.  `TYPE(id="element_id", text="text_to_type", reason="why")`: Type text into an Input or Textarea. Use the id provided.
3.  `SELECT(id="element_id", value="option_value", reason="why")`: Select an option from a Select dropdown. Use the id provided and the value attribute of the option.
4.  `SCROLL(direction="down|up", reason="why")`: Scroll the page down or up to find more content.
5.  `EXTRACT(data_description="what to extract", reason="why")`: If you believe the needed information is visible, use this action. Describe the specific piece of data.
6.  `GO_BACK(reason="why")`: Navigate back to the previous page.
7.  `FINISH(answer="final answer", reason="why")`: Use this if you have found the final answer to the original goal. The answer should be concise.
8.  `FAIL(reason="why")`: Use this if you are stuck, cannot find the information, or encountered an error.

Choose the *single* best action to take *right now* to progress towards the goal. Provide your response as a JSON object containing 'action', 'reason', and any necessary parameters (like 'id', 'text', 'value', 'data_description', 'answer', 'direction').
Example: {"action": "CLICK", "id": "5", "reason": "This link seems relevant to the CPI data."}
Example: {"action": "TYPE", "id": "12", "text": "Delhi", "reason": "Entering the city name into the search field."}
Example: {"action": "FINISH", "answer": "The CPI for Delhi in March 2024 was 185.2.", "reason": "Found the specific data point requested."}
Example: {"action": "SCROLL", "direction": "down", "reason": "The information might be further down the page."}
"""

    prompt_history = "\n".join([f"Step {i+1}: {h}" for i, h in enumerate(history[-5:])]) # Include last 5 actions/observations

    messages = [
        SystemMessage(content=(
            "You are an Autonomous Web Browse Agent. Your goal is to navigate web pages and extract specific information. "
            "You will be given the original user goal, a representation of the current web page (URL, text snippet, interactive elements with IDs), "
            "a history of recent actions, and a list of available actions. "
            "Analyze the current page content and choose the *single best action* to take next to achieve the goal. "
            "Be methodical. Prioritize actions that seem most likely to lead directly to the answer. "
            f"Focus ONLY on the goal: '{goal}'. Respond ONLY with a valid JSON object representing your chosen action."
        )),
        HumanMessage(content=(
            f"Current Goal: {goal}\n\n"
            f"Recent History:\n{prompt_history}\n\n"
            f"Current Page State:\n{page_representation}\n\n"
            f"Available Actions:\n{action_descriptions}\n\n"
            "Your Action (JSON only):"
        ))
    ]

    try:
        response = await llm.ainvoke(input=messages)
        action_str = response.content.strip()

        # Clean potential markdown/formatting issues
        if action_str.startswith("```json"):
            action_str = action_str[7:]
        if action_str.endswith("```"):
            action_str = action_str[:-3]
        action_str = action_str.strip()

        logger.debug(f"LLM Raw Action Response: {action_str}")
        action_json = json.loads(action_str)

        # Basic validation
        if "action" not in action_json:
            raise ValueError("LLM response missing 'action' field.")

        logger.info(f"LLM decided action: {action_json.get('action')}, Reason: {action_json.get('reason', 'N/A')}")
        return action_json

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}\nRaw response: {action_str}")
        return {"action": "fail", "reason": f"LLM generated invalid JSON: {action_str}"}
    except Exception as e:
        logger.error(f"Error invoking LLM for action: {e}")
        return {"action": "fail", "reason": f"LLM invocation error: {e}"}


async def execute_action(page: Page, action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Executes the action decided by the LLM using Playwright.

    Returns:
        Tuple[bool, Optional[str]]: (action_successful, potential_extracted_data_or_answer)
    """
    action_name = action.get("action", "").upper()
    element_id = action.get("id")
    reason = action.get("reason", "N/A") # Useful for logging

    logger.info(f"Executing action: {action_name} (Reason: {reason})")

    try:
        target_element: Optional[Locator] = None
        if element_id is not None:
            selector = f"[{BWE_ID_ATTRIBUTE}='{element_id}']"
            target_element = page.locator(selector).first # Use first() to avoid ambiguity if somehow IDs weren't unique
            # Wait briefly for the element to be potentially available
            try:
                await target_element.wait_for(state='visible', timeout=5000)
            except Exception:
                logger.warning(f"Element with id {element_id} not found or not visible for action {action_name}.")
                # Some actions might not strictly need visibility (like type), but most do.
                # Let specific actions handle the error if needed.
                pass # Continue and let the action try


        if action_name == "CLICK":
            if not target_element: return False, f"Click failed: Element with id {element_id} not found."
            await target_element.click(timeout=10000)
            # Wait for potential navigation or dynamic content loading
            await page.wait_for_load_state('domcontentloaded', timeout=15000)


        elif action_name == "TYPE":
            text_to_type = action.get("text")
            if not target_element: return False, f"Type failed: Element with id {element_id} not found."
            if text_to_type is None: return False, "Type failed: Missing 'text' parameter."
            # Consider clicking first to ensure focus
            await target_element.click(timeout=5000)
            await target_element.fill(text_to_type, timeout=10000)
             # Optional: Press Enter if it's a search box (LLM might need to specify this)
            if action.get("press_enter", False):
                 await target_element.press("Enter", timeout=5000)
                 await page.wait_for_load_state('domcontentloaded', timeout=15000)

        elif action_name == "SELECT":
            value_to_select = action.get("value")
            if not target_element: return False, f"Select failed: Element with id {element_id} not found."
            if value_to_select is None: return False, "Select failed: Missing 'value' parameter."
            await target_element.select_option(value_to_select, timeout=10000)
            await page.wait_for_load_state('domcontentloaded', timeout=15000) # Selection might trigger reload


        elif action_name == "SCROLL":
            direction = action.get("direction", "down")
            scroll_amount = 500 # Adjust as needed
            if direction == "down":
                await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            elif direction == "up":
                 await page.evaluate(f"window.scrollBy(0, -{scroll_amount})")
            else:
                return False, f"Scroll failed: Invalid direction '{direction}'."
            await asyncio.sleep(1) # Give time for any lazy-loaded content

        elif action_name == "EXTRACT":
            data_description = action.get("data_description")
            if not data_description: return False, "Extract failed: Missing 'data_description'."
            # This is a placeholder. A real implementation might involve:
            # 1. Getting the simplified page content again.
            # 2. Making *another* LLM call specifically asking it to extract
            #    the `data_description` from the provided text.
            logger.info(f"Attempting extraction for: {data_description}")
            # Simulate asking LLM to extract from current simplified view
            current_url, page_repr = await simplify_page_for_llm(page)
            # --- Placeholder for actual extraction LLM call ---
            # extracted_data = await ask_llm_to_extract(llm, data_description, page_repr)
            extracted_data = f"Placeholder: Extracted '{data_description}' based on current view."
            # For now, just return the description indicating intent
            return True, extracted_data # Signal success but return the request description

        elif action_name == "GO_BACK":
             await page.go_back(wait_until='domcontentloaded', timeout=15000)

        elif action_name == "FINISH":
            answer = action.get("answer", "No specific answer provided.")
            return True, answer # Signal successful completion with the answer

        elif action_name == "FAIL":
            fail_reason = action.get("reason", "No specific reason provided.")
            return False, f"LLM indicated failure: {fail_reason}" # Signal failure

        else:
            return False, f"Unknown action: {action_name}"

        # If we reached here, the action was likely successful (unless it was FINISH/FAIL/EXTRACT)
        return True, None

    except Exception as e:
        logger.error(f"Error executing action {action_name} (Element ID: {element_id}): {e}")
        try:
             # Save screenshot for debugging if action fails
             await page.screenshot(path=f"error_action_{action_name}_{element_id}.png")
        except Exception as screenshot_err:
             logger.error(f"Could not save error screenshot: {screenshot_err}")
        return False, f"Execution error: {e}"


# --- Main Agent Function ---

async def browse_and_extract(llm_instance: BaseLanguageModel, initial_query: str, max_steps: int = MAX_BROWSE_STEPS):
    """
    Main agent function to perform search and interact with pages.
    """
    global llm # Allow modification if needed, though passed as arg is better
    llm = llm_instance # Use the passed LLM instance

    if not llm:
        logger.error("LLM instance is required.")
        return "Error: LLM not initialized."

    logger.info(f"Starting Browse task for query: '{initial_query}'")

    refined_query = await refine_search_query(llm, initial_query)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) # Use headless=False for debugging
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            java_script_enabled=True, # Essential for modern websites
            accept_downloads=False,
            ignore_https_errors=True # Be cautious with this in production
        )
        # Block common annoyances - adjust as needed
        await context.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())

        try:
            search_results = await search_google(refined_query, context)

            if not search_results:
                logger.warning("No search results found.")
                return "Could not find relevant information: No search results."

            logger.info(f"Top {len(search_results)} search results to investigate:")
            for i, res in enumerate(search_results):
                logger.info(f"  {i+1}. {res['title']} ({res['url']})")


            # --- Iterate through results and attempt interaction ---
            final_answer = None
            for i, result in enumerate(search_results):
                logger.info(f"\n--- Investigating Result {i+1}/{len(search_results)}: {result['title']} ---")
                page = await context.new_page()
                history = [] # Reset history for each page/result
                try:
                    logger.info(f"Navigating to: {result['url']}")
                    await page.goto(result['url'], wait_until='domcontentloaded', timeout=30000)

                    for step in range(max_steps):
                        logger.info(f"--- Step {step + 1}/{max_steps} on {page.url} ---")

                        # Handle potential popups/dialogs simply by closing them
                        page.once("dialog", lambda dialog: asyncio.ensure_future(dialog.dismiss()))

                        current_url, page_repr = await simplify_page_for_llm(page)
                        history.append(f"Observation: Currently on {current_url}. Content simplified.")

                        action_json = await ask_llm_for_action(llm, initial_query, page_repr, history)

                        if not action_json:
                           logger.error("Failed to get action from LLM.")
                           history.append("Action: Failed to get action from LLM.")
                           break # Stop processing this page

                        history.append(f"Action Chosen: {action_json}")
                        action_name = action_json.get("action", "").upper()

                        if action_name in ["FINISH", "FAIL"]:
                            success = action_name == "FINISH"
                            message = action_json.get("answer" if success else "reason", "N/A")
                            logger.info(f"LLM decided to {action_name}. Message: {message}")
                            if success:
                                final_answer = message
                            break # Stop processing this page

                        # Execute the action
                        success, message = await execute_action(page, action_json)
                        history.append(f"Action Result: {'Success' if success else 'Failed'}. {message or ''}")

                        if not success:
                            logger.warning(f"Action {action_name} failed. Reason: {message}")
                            # Decide if we should stop or let the LLM try again
                            # For now, we'll let the LLM see the failure in history and decide
                            # break # Option: Stop on first failure


                        # Small delay to mimic human interaction and prevent rate limiting
                        await asyncio.sleep(1.5)

                    else: # Loop finished without break (max_steps reached)
                         logger.warning(f"Max steps ({max_steps}) reached for {result['url']}.")

                except Exception as e:
                    logger.error(f"Error processing page {result['url']}: {e}")
                    try:
                        await page.screenshot(path=f"error_page_{i+1}.png")
                    except Exception as se:
                         logger.error(f"Failed to save error screenshot for page {i+1}: {se}")

                finally:
                    if 'page' in locals() and not page.is_closed():
                         await page.close()

                # If we found an answer, stop trying other results
                if final_answer:
                    logger.info("Found final answer. Stopping search.")
                    break

            # --- End of search result iteration ---
            if final_answer:
                return f"Success: {final_answer}"
            else:
                logger.warning("Could not find the answer after checking top search results.")
                return "Could not extract the required information after trying multiple sources."

        except Exception as e:
            logger.error(f"An unexpected error occurred during the Browse process: {e}", exc_info=True)
            return f"An error occurred: {e}"
        finally:
             logger.info("Closing browser context.")
             await context.close()
             await browser.close()


# --- Example Usage ---

async def main():
    # IMPORTANT: Replace this with your actual LLM initialization
    # Make sure the LLM model used is capable of JSON output and reasoning.
    try:
        from langchain_openai import ChatOpenAI # Example
        # Load API key from environment
        from dotenv import load_dotenv
        load_dotenv()
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            print("ERROR: OPENAI_API_KEY not found in environment variables.")
            print("Please set it or replace the LLM initialization code.")
            return

        llm_instance = ChatOpenAI(model="gpt-4o", temperature=0.0, api_key=openai_api_key,
                                  model_kwargs={"response_format": {"type": "json_object"}}) # Force JSON output if supported
    except ImportError:
        print("ERROR: Langchain OpenAI not installed (`pip install langchain-openai python-dotenv`).")
        print("You need to initialize a suitable LLM instance.")
        return
    except Exception as e:
        print(f"Error initializing LLM: {e}")
        return


    # --- Test Queries ---
    # query = "What is the current population of India according to the World Bank?"
    query = "give me the cpi index of delhi for the latest available month"
    # query = "Who is the current CEO of Google?"
    # query = "Summarize the main points of the latest article on the front page of bbc.com/news"

    result = await browse_and_extract(llm_instance, query)
    print("\n" + "="*30 + " FINAL RESULT " + "="*30)
    print(result)
    print("="*74)


if __name__ == "__main__":
    # Ensure OPENAI_API_KEY is set in your environment or .env file
    # Run the async main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")