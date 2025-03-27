import asyncio,os
import json,openai
from openai import AsyncOpenAI

import markdownify
from langchain_core.prompts import PromptTemplate
from playwright.async_api import async_playwright

# Set your OpenAI API key here or via environment variables
from dotenv import load_dotenv

load_dotenv()

aclient = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Function Definitions ---

async def search_google(params, browser):
    """
    Performs a Google search and extracts the URLs and titles from the search results.
    """
    page = await browser.get_current_page()
    query = params.get("query")
    url = f'https://www.google.com/search?q={query}&udm=14'
    await page.goto(url)
    await page.wait_for_load_state()
    
    search_results = await page.evaluate('''() => {
        return Array.from(document.querySelectorAll('a h3')).map(h => ({
            title: h.innerText,
            url: h.parentElement.href
        })).slice(0, 10);
    }''')
    
    msg = f'🔍  Searched for "{query}" in Google'
    print("search_google msg:", msg)
    return search_results


async def go_to_url(params, browser):
    """
    Navigates to the specified URL.
    """
    page = await browser.get_current_page()
    url = params.get("url")
    await page.goto(url)
    await page.wait_for_load_state()
    msg = f'🔗  Navigated to {url}'
    print("go_to_url msg:", msg)
    return msg


async def wait(seconds: int = 3):
    """
    Waits for a given number of seconds.
    """
    msg = f'🕒  Waiting for {seconds} seconds'
    print("wait msg:", msg)
    await asyncio.sleep(seconds)
    return msg


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
        # print("extract_content msg:", msg)
        return msg
    except Exception as e:
        print("extract_content error:", e)
        msg = f'📄  Extracted from page:\n{content}\n'
        return msg


# --- Helper Classes ---

class BrowserWrapper:
    """
    A simple wrapper to hold the current Playwright page.
    """
    def __init__(self, page):
        self.page = page

    async def get_current_page(self):
        return self.page


class OpenAIGPT:
    """
    Uses OpenAI's ChatCompletion to analyze function outputs and decide the next action.
    """
    async def analyze(self, input_text: str) -> dict:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a web scraper controller that decides the next action based on the output of previous function calls. "
                    "Return a JSON object that strictly follows one of these formats:\n"
                    '- For navigation: {"action": "go_to_url", "url": "https://example.com"}\n'
                    '- For waiting: {"action": "wait", "seconds": 3}\n'
                    '- For content extraction: {"action": "extract_content"}\n'
                    '- To finish: {"action": "final", "output": "Final message here. It Should summarize the given content"}\n'
                    "Do not include any extra text."
                )
            },
            {"role": "user", "content": f"Input: {input_text}"}
        ]
        # print("message",messages)
        response = await aclient.chat.completions.create(model="gpt-4o",
        messages=messages,
        temperature=0.0)
        
        print("results", response)
        
        # Corrected way to access content
        answer = response.choices[0].message.content.strip()

        try:
            result = json.loads(answer)
        except Exception as e:
            # If JSON parsing fails, default to finishing the process.
            result = {"action": "final", "output": f"Failed to parse GPT output: {answer}"}
        
        print("OpenAIGPT analyze output:", result)
        return result


class OpenAIPageExtractionLLM:
    """
    Uses OpenAI's ChatCompletion to extract content from the page based on a given prompt.
    """
    async def invoke(self, prompt: str):
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a page extraction assistant. Extract the relevant information based on the provided goal and page. "
                    "Return your response in JSON format without any additional text."
                )
            },
            {"role": "user", "content": prompt}
        ]
        response = await aclient.chat.completions.create(model="gpt-4o",
        messages=messages,
        temperature=0.0)
        answer = response.choices[0].message['content'].strip()

        # A simple object to hold the output content.
        class Output:
            def __init__(self, content):
                self.content = content

        print("OpenAIPageExtractionLLM invoke output:", answer)
        return Output(content=answer)


# --- Orchestrator Function ---

async def ai_web_scraper(user_prompt, browser, page_extraction_llm, gpt_llm):
    """
    Orchestrates the AI web scraper:
      1. Always starts with a Google search.
      2. Passes the output to GPT for analysis.
      3. Calls the next function as instructed.
      4. Loops until a final outcome is reached.
    """
    # Step 1: Start with a Google search.
    result = await search_google(params={'query': user_prompt}, browser=browser)
    print("Search result:", result)

    # Analyze the output with GPT.
    analysis = await gpt_llm.analyze(result)
    print("GPT analysis:", analysis)

    # Main loop: continue until GPT signals final outcome.
    while True:
        action = analysis.get("action")
        if action == "go_to_url":
            url = analysis.get("url")
            if not url:
                print("No URL provided in GPT response; ending scraping.")
                break
            result = await go_to_url(params={'url': url}, browser=browser)
            print("go_to_url result:", result)

        elif action == "wait":
            seconds = analysis.get("seconds", 3)
            result = await wait(seconds=seconds)
            print("wait result:", result)

        elif action == "extract_content":
            result = await extract_content(goal=user_prompt, browser=browser, page_extraction_llm=page_extraction_llm)
            print("extract_content result:", result)

        elif action == "final":
            final_output = analysis.get("output", "Final outcome reached")
            print("Final outcome:", final_output)
            return final_output

        else:
            print("No further actions specified by GPT. Ending process.")
            break

        # Analyze the output after each function call.
        analysis = await gpt_llm.analyze(result)
        print("New GPT analysis:", analysis)

    return "Scraper finished execution without a final outcome."


# --- Main Entry Point ---

async def main():
    user_prompt = "What are the latest trends in AI?"
    async with async_playwright() as p:
        browser_instance = await p.chromium.launch(args=[
				'--no-sandbox',
				'--disable-blink-features=AutomationControlled',
				'--disable-infobars',
				'--disable-background-timer-throttling',
				'--disable-popup-blocking',
				'--disable-backgrounding-occluded-windows',
				'--disable-renderer-backgrounding',
				'--disable-window-activation',
				'--disable-focus-on-load',
				'--no-first-run',
				'--no-default-browser-check',
				'--no-startup-window',
				'--window-position=0,0',
			],headless=False)  # Change to True to run headless.
        context = await browser_instance.new_context()
        page = await context.new_page()

        # Wrap the page in our BrowserWrapper.
        browser_wrapper = BrowserWrapper(page)

        # Instantiate our OpenAI GPT and page extraction LLM.
        gpt_llm = OpenAIGPT()
        page_extraction_llm = OpenAIPageExtractionLLM()

        # Run the orchestrator.
        final_output = await ai_web_scraper(user_prompt, browser_wrapper, page_extraction_llm, gpt_llm)
        print("Final output:", final_output)

        await browser_instance.close()

if __name__ == "__main__":
    asyncio.run(main())
