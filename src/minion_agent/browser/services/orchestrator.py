import logging
from src.minion_agent.browser.services.google_search import search_google, search_next_page, refine_search_query
from src.minion_agent.browser.services.navigation import go_to_url
from src.minion_agent.browser.services.content_extraction import extract_content
from src.minion_agent.browser.services.interactive_actions import perform_page_interactions
from src.minion_agent.browser.utils.helpers import save_output, format_context_for_display

logger = logging.getLogger(__name__)

async def ai_web_scraper(user_prompt: str, browser, page_extraction_llm, gpt_llm, mcp_planner=None) -> str:
    """
    Orchestrates the web scraping:
      1. Perform a Google search.
      2. Iterate through search result URLs.
      3. For each URL, navigate and extract content using function calling.
      4. If extraction returns 'next_url', skip to the next link.
      5. If 'final', return the answer.
      6. If all links are exhausted, try the next page or finish.
      
    If MCP planner is provided, it will be used to manage context and make decisions.
    """
    # If MCP planner is used, let it guide the process
    if mcp_planner:
        return await mcp_guided_scraping(user_prompt, browser, page_extraction_llm, gpt_llm, mcp_planner)
    
    # Otherwise, use the original algorithm
    refined_query = await refine_search_query(gpt_llm, user_prompt)
    search_results = await search_google(refined_query, browser)
    current_index = 0
    while True:
        if current_index < len(search_results):
            current_url = search_results[current_index]["url"]
            logger.info(f"Processing URL {current_index+1}/{len(search_results)}: {current_url}")
            try:
                await go_to_url(current_url, browser)
            except Exception as e:
                logger.error(f"Navigation error for {current_url}: {e}. Attempting to go back and skip.")
                try:
                    await browser.go_back()
                except Exception:
                    pass
                current_index += 1
                continue

            try:
                extraction_result = await extract_content(user_prompt, browser, page_extraction_llm, target_selector="div#main")
            except Exception as e:
                logger.error(f"Extraction error for {current_url}: {e}")
                extraction_result = {"action": "next_url", "summary": "", "key_points": [], "context": "", "output": ""}

            action_type = extraction_result.get("action", "next_url")
            if action_type == "final":
                final_output = extraction_result.get("output", "Final outcome reached")
                save_output("final_output.txt", final_output)
                return final_output
            else:
                current_index += 1
                continue

        else:
            new_results = await search_next_page(browser)
            if new_results:
                search_results = new_results
                current_index = 0
                continue
            else:
                logger.info("No further search results available.")
                return "Scraper finished execution without a final outcome."

async def mcp_guided_scraping(user_prompt: str, browser, page_extraction_llm, gpt_llm, mcp_planner) -> str:
    """
    MCP-guided web scraping that uses the planner to make decisions about next actions.
    """
    # Start from the initial state
    current_url = None
    
    while mcp_planner.should_continue_scraping():
        # Use the MCP planner to decide the next action
        action_data = await mcp_planner.decide_next_action(user_prompt, current_url)
        action = action_data.get("action", "").upper()
        
        logger.info(f"MCP planner decided action: {action}")
        
        if action == "SEARCH":
            # Perform a search
            search_query = action_data.get("query", user_prompt)
            refined_query = await refine_search_query(gpt_llm, search_query)
            
            # Add the query to the context
            mcp_planner.add_search_query(refined_query)
            
            # Execute the search
            search_results = await search_google(refined_query, browser)
            
            # Make sure to store search results in a way that preserves them
            if not mcp_planner.context.get("search_results"):
                mcp_planner.context["search_results"] = search_results
            else:
                # Only add new results
                existing_urls = {result["url"] for result in mcp_planner.context["search_results"]}
                new_results = [result for result in search_results if result["url"] not in existing_urls]
                mcp_planner.context["search_results"].extend(new_results)
                
            logger.info(f"Search results available: {len(mcp_planner.context['search_results'])}")
            mcp_planner.state = "SEARCH_RESULTS_AVAILABLE"
            
        elif action == "NAVIGATE":
            # Navigate to a URL
            url_to_navigate = action_data.get("url")
            
            # If URL is example.com or not provided, use a real search result instead
            if not url_to_navigate or "example.com" in url_to_navigate:
                logger.warning(f"Invalid URL detected: {url_to_navigate}, trying to use a search result instead")
                search_results = mcp_planner.context.get("search_results", [])
                
                if search_results:
                    # Find a search result that hasn't been visited yet
                    visited_urls = set(mcp_planner.context.get("visited_urls", []))
                    unvisited_results = [r for r in search_results if r.get("url") not in visited_urls]
                    
                    if unvisited_results:
                        url_to_navigate = unvisited_results[0].get("url")
                        logger.info(f"Using unvisited search result: {url_to_navigate}")
                    else:
                        # If all have been visited, just use the first one
                        url_to_navigate = search_results[0].get("url")
                        logger.info(f"All results visited, reusing: {url_to_navigate}")
            
            # Log the chosen URL
            logger.info(f"Navigating to URL: {url_to_navigate}")
            
            if url_to_navigate:
                try:
                    current_url = url_to_navigate
                    await go_to_url(current_url, browser)
                    mcp_planner.add_visited_url(current_url)
                    
                    # Perform interactive actions first to improve page exploration
                    logger.info("Performing interactive actions on the page")
                    try:
                        interaction_results = await perform_page_interactions(browser, user_prompt)
                        mcp_planner.update_context("interactive_actions", interaction_results)
                        logger.info(f"Interactive actions performed: {interaction_results.get('actions_performed', [])}")
                    except Exception as e:
                        logger.error(f"Error during interactive actions: {e}")
                    
                    # Wait briefly after interactions
                    import asyncio
                    await asyncio.sleep(1)
                    
                    # Then extract content
                    logger.info("Performing automatic extraction after navigation and interactions")
                    try:
                        extraction_result = await extract_content(
                            user_prompt, browser, page_extraction_llm, target_selector="div#main"
                        )
                        mcp_planner.add_extracted_content(current_url, extraction_result)
                        
                        if extraction_result.get("action") == "final":
                            # This page has the final answer
                            mcp_planner.state = "FINAL_ANSWER_FOUND"
                        else:
                            # This page doesn't have what we're looking for
                            mcp_planner.state = "EXTRACTION_COMPLETE"
                    except Exception as e:
                        logger.error(f"Extraction error during automatic extraction: {e}")
                        mcp_planner.state = "PAGE_LOADED"
                except Exception as e:
                    logger.error(f"Navigation error: {e}")
                    current_url = None
                    mcp_planner.state = "NAVIGATION_ERROR"
            else:
                # Try to get next page of search results
                new_results = await search_next_page(browser)
                if new_results:
                    mcp_planner.update_context("search_results", new_results)
                    mcp_planner.state = "SEARCH_RESULTS_AVAILABLE"
                else:
                    logger.warning("No URL to navigate to and no more search results")
                    mcp_planner.state = "NO_MORE_RESULTS"
        
        elif action == "EXTRACT":
            # Extract content from the current page
            if current_url:
                # Try interactive actions first
                logger.info("Performing interactive actions during EXTRACT")
                try:
                    interaction_results = await perform_page_interactions(browser, user_prompt)
                    mcp_planner.update_context("interactive_actions", interaction_results)
                    logger.info(f"Interactive actions performed: {interaction_results.get('actions_performed', [])}")
                    
                    # Wait briefly after interactions
                    import asyncio
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Error during interactive actions in EXTRACT: {e}")
                
                # Now extract the content
                try:
                    extraction_result = await extract_content(
                        user_prompt, browser, page_extraction_llm, target_selector="div#main"
                    )
                    mcp_planner.add_extracted_content(current_url, extraction_result)
                    
                    if extraction_result.get("action") == "final":
                        # This page has the final answer
                        mcp_planner.state = "FINAL_ANSWER_FOUND"
                    else:
                        # This page doesn't have what we're looking for
                        mcp_planner.state = "EXTRACTION_COMPLETE"
                        
                except Exception as e:
                    logger.error(f"Extraction error: {e}")
                    mcp_planner.state = "EXTRACTION_ERROR"
            else:
                logger.warning("Cannot extract - no current URL")
                mcp_planner.state = "NO_CURRENT_PAGE"
        
        elif action == "FINISH":
            # Generate and return the final answer
            final_answer = await mcp_planner.generate_final_answer(user_prompt)
            
            # Format and save the context for debugging/review
            context_display = format_context_for_display(mcp_planner.context)
            save_output("mcp_context_summary.md", context_display)
            
            # Save the final answer
            save_output("final_output.txt", final_answer)
            
            return final_answer
            
        else:
            logger.warning(f"Unknown action: {action}")
    
    # If we've exited the loop without a final answer (e.g., reached max URLs),
    # generate a final answer from whatever we've collected
    return await mcp_planner.generate_final_answer(user_prompt)