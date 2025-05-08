import logging
import asyncio
from typing import List, Dict, Any, Union
from src.minion_agent.browser.services.google_search import (
    search_google, search_next_page, refine_search_query
)
from src.minion_agent.browser.services.navigation import go_to_url
from src.minion_agent.browser.services.content_extraction import extract_content
from src.minion_agent.browser.utils.helpers import save_output, format_context_for_display
from src.minion_agent.browser.utils.browser_wrapper import BrowserWrapper  # adjust import path as needed

logger = logging.getLogger(__name__)

async def snapshot_interactive_elements(page_or_wrapper) -> List[Dict[str, str]]:
    """
    Return up to 20 interactive elements with selectors and label/text,
    including checkboxes, radios, selects, inputs, links, and buttons.
    Unwraps BrowserWrapper if needed, uses Playwright Page methods.
    """
    # unwrap wrapper if needed
    if hasattr(page_or_wrapper, 'get_current_page'):
        page = await page_or_wrapper.get_current_page()
    else:
        page = page_or_wrapper

    elements: List[Dict[str, str]] = []
    # 1) labels with inputs (checkboxes, radios)
    labels = await page.query_selector_all("label")
    for lbl in labels[:20]:
        text = (await lbl.text_content() or "").strip()
        inp = await lbl.query_selector("input[type=checkbox], input[type=radio]")
        if inp:
            sel = f"label:has-text(\"{text}\") input"
            elements.append({"selector": sel, "text": text})
    # 2) selects (dropdowns)
    selects = await page.query_selector_all("select")
    for sel in selects[:10]:
        ident = await sel.get_attribute("id") or await sel.get_attribute("name")
        if ident:
            elements.append({"selector": f"select#{ident}", "text": "<dropdown>"})
    # 3) text/search inputs
    inputs = await page.query_selector_all("input[type=text], input[type=search]")
    for inp in inputs[:10]:
        ph = (await inp.get_attribute("placeholder") or "").strip()
        sel = f"input[placeholder=\"{ph}\"]" if ph else "input[type=text]"
        elements.append({"selector": sel, "text": ph or "<text>"})
    # 4) hyperlinks
    links = await page.query_selector_all("a[href]")
    for link in links[:20]:
        text = (await link.text_content() or "").strip()
        href = await link.get_attribute("href") or ""
        # CSS-escape quotes in href
        sel = f"a[href=\"{href}\"]"
        elements.append({"selector": sel, "text": text or href})
    # 5) buttons
    buttons = await page.query_selector_all("button")
    for btn in buttons[:10]:
        text = (await btn.text_content() or "").strip()
        btn_id = await btn.get_attribute("id")
        if btn_id:
            sel = f"button#{btn_id}"
        else:
            sel = f"button:has-text(\"{text}\")"
        elements.append({"selector": sel, "text": text or "<button>"})
    return elements


async def ai_web_scraper(
    user_prompt: str,
    page: Union[BrowserWrapper, Any],  # Playwright Page or BrowserWrapper
    page_extraction_llm,
    gpt_llm,
    mcp_planner=None
) -> str:
    if not mcp_planner:
        raise RuntimeError("MCP planner is required for LLM-guided scraping.")
    return await mcp_guided_scraping(
        user_prompt, page, page_extraction_llm, gpt_llm, mcp_planner
    )

async def mcp_guided_scraping(
    user_prompt: str,
    page: Union[BrowserWrapper, Any],  # Playwright Page or BrowserWrapper
    page_extraction_llm,
    gpt_llm,
    mcp_planner
) -> str:
    current_url = None
    while mcp_planner.should_continue_scraping():
        # decide with or without page_elements based on current_url
        elements = None
        if current_url:
            elements = await snapshot_interactive_elements(page)
            logger.info(f"page elements>>>> {elements}")
        action_data = await mcp_planner.decide_next_action(
            user_goal=user_prompt,
            current_url=current_url,
            page_elements=elements
        )
        action = action_data.get("action", "").upper()
        logger.info(f"Planner → {action}")

        # Handle custom planner action 'NEXT_URL' as NAVIGATE
        if action == "NEXT_URL":
            action = "NAVIGATE"

        # If planner signals FINISH but no real extraction happened, ignore
        if action == "FINISH":
            # check if any extracted content has meaningful output or final flag
            has_data = any(
                (c["content"].get("action") == "final") or bool(c["content"].get("output"))
                for c in mcp_planner.context.get("extracted_content", [])
            )
            if not has_data:
                logger.info("Planner requested FINISH but no data collected—continuing scraping")
                continue  # skip finish and keep looping

        if action == "SEARCH":
            query = action_data.get("query", user_prompt)
            refined = await refine_search_query(gpt_llm, query)
            mcp_planner.add_search_query(refined)
            results = await search_google(refined, page)
            # Add the query to the context
            mcp_planner.add_search_query(refined)
            
            # Execute the search
            # search_results = await search_google(refined, browser)
            
            # Make sure to store search results in a way that preserves them
            if not mcp_planner.context.get("search_results"):
                logger.info(f"results>>>> : {results}")
                mcp_planner.context["search_results"] = results
            else:
                # Only add new results
                existing_urls = {result["url"] for result in mcp_planner.context["search_results"]}
                new_results = [result for result in results if result["url"] not in existing_urls]
                mcp_planner.context["search_results"].extend(new_results)
                
            logger.info(f"Search results available: {len(mcp_planner.context['search_results'])}")
            mcp_planner.state = "SEARCH_RESULTS_AVAILABLE"
            continue

        if action == "NAVIGATE":
            url = action_data.get("url")
            if not url:
                sr = mcp_planner.context.get("search_results", [])
                url = sr[0]["url"] if sr else None
            if not url:
                nxt = await search_next_page(page)
                if nxt:
                    mcp_planner.context["search_results"] = nxt
                    continue
                break
            current_url = url
            # unwrap and goto
            if hasattr(page, 'goto'):
                await page.goto(current_url)
            else:
                await go_to_url(current_url, page)
            mcp_planner.add_visited_url(current_url)
            try:
                extract_res = await extract_content(
                    user_prompt, page, page_extraction_llm, target_selector="div#main"
                )
                logger.info(f"exxtracted res>>>: {extract_res}")
                mcp_planner.add_extracted_content(current_url, extract_res)
                mcp_planner.state = "DONE" if extract_res.get("action")=="final" else "EXTRACTED"
            except Exception as e:
                logger.error(f"Extract error: {e}")
                mcp_planner.state = "ERROR"

        elif action == "PAGE_INTERACTIONS":
            for it in action_data.get("interactions", []):
                sel = it.get("selector")
                typ = it.get("type")
                val = it.get("value")
                # unwrap
                page_obj = await page.get_current_page() if hasattr(page, 'get_current_page') else page
                try:
                    elem = await page_obj.query_selector(sel)
                    if not elem:
                        logger.warning(f"No element for selector {sel}")
                        continue
                    if typ == "click":
                        await elem.click()
                    elif typ == "select":
                        await page_obj.select_option(sel, val)
                    elif typ in ("type", "fill"):
                        await elem.fill(val)
                    await asyncio.sleep(1)
                    logger.info(f"Interacted {typ} on {sel}")
                except Exception as e:
                    logger.warning(f"Failed interaction {typ} on {sel}: {e}")
            try:
                post_res = await extract_content(
                    user_prompt, page, page_extraction_llm, target_selector="div#main"
                )
                mcp_planner.add_extracted_content(current_url, post_res)
                mcp_planner.state = "CURRENT_DONE" if post_res.get("action")=="final" else "EXTRACTED"
            except Exception as e:
                logger.error(f"Post-interact extract error: {e}")
                mcp_planner.state = "ERROR"

        elif action == "EXTRACT":
            if current_url:
                try:
                    res = await extract_content(
                        user_prompt, page, page_extraction_llm, target_selector="div#main"
                    )
                    mcp_planner.add_extracted_content(current_url, res)
                    mcp_planner.state = "CURRENT_DONE" if res.get("action")=="final" else "EXTRACTED"
                except Exception as e:
                    logger.error(f"Extract error: {e}")
                    mcp_planner.state = "ERROR"
            else:
                continue

        elif action == "FINISH":
            answer = await mcp_planner.generate_final_answer(user_prompt)
            save_output("final_output.txt", answer)
            summary = format_context_for_display(mcp_planner.context)
            save_output("mcp_context_summary.md", summary)
            return answer

        else:
            logger.warning(f"Unknown action {action}, default EXTRACT")
            mcp_planner.state = "DEFAULT"

    return await mcp_planner.generate_final_answer(user_prompt)