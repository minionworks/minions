import logging
import markdownify

logger = logging.getLogger(__name__)

async def extract_content(goal: str, browser, page_extraction_llm, target_selector: str = None) -> dict:
    """
    Extract page content using multiple potential selectors, then call the function-based LLM
    to determine if it answers the question. Returns a dict with {action, summary, key_points, context, output}.
    """
    page = await browser.get_current_page()
    common_selectors = ["div#main", "main", "div.main", "div#content", "div.content"]
    selectors_to_try = [target_selector] + common_selectors if target_selector else common_selectors

    content_html = ""
    for selector in selectors_to_try:
        if not selector:
            continue
        try:
            element = await page.query_selector(selector)
            if element:
                content_html = await element.inner_html()
                logger.info(f"Found content using selector '{selector}'")
                break
        except Exception as e:
            logger.warning(f"Error using selector '{selector}': {e}")

    if not content_html:
        logger.warning("No content element found with common selectors; using full page content.")
        try:
            content_html = await page.content()
        except Exception as e:
            logger.error(f"Error obtaining full page content: {e}")
            content_html = ""

    # Convert HTML to Markdown.
    content_markdown = markdownify.markdownify(content_html)
    return await page_extraction_llm.extract_with_function_call(content_markdown, goal)
