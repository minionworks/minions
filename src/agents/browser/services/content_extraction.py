from langchain_core.prompts import PromptTemplate
import markdownify

async def extract_content(goal: str, browser, page_extraction_llm):
    """
    Extracts and processes the page content.
    Uses markdownify to convert HTML to Markdown, then sends the content with the goal
    to a page extraction LLM.
    """
    page = await browser.get_current_page()
    content_html = await page.content()
    content = markdownify.markdownify(content_html)

    prompt = (
        "Your task is to extract the content of the page. You will be given a page "
        "and a goal and you should extract all relevant information around this goal from the page. "
        "If the goal is vague, summarize the page. Respond in JSON format. "
        "Extraction goal: {goal}, Page: {page}"
    )
    template = PromptTemplate(input_variables=['goal', 'page'], template=prompt)
    formatted_prompt = template.format(goal=goal, page=content)
    try:
        output = await page_extraction_llm.invoke(formatted_prompt)
        msg = f'📄  Extracted from page:\n{output.content}\n'
        return msg
    except Exception as e:
        print("extract_content error:", e)
        msg = f'📄  Extracted from page:\n{content}\n'
        return msg