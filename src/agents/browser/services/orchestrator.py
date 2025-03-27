from src.services.google_search import search_google
from src.services.navigation import go_to_url
from src.services.content_extraction import extract_content

async def ai_web_scraper(user_prompt, browser, page_extraction_llm, gpt_llm):
    result = await search_google(params={'query': user_prompt}, browser=browser)
    analysis = await gpt_llm.analyze(result)

    while True:
        action = analysis.get("action")
        if action == "go_to_url":
            url = analysis.get("url")
            if not url:
                break
            result = await go_to_url(params={'url': url}, browser=browser)

        elif action == "wait":
            seconds = analysis.get("seconds", 3)
            result = await wait(seconds=seconds)

        elif action == "extract_content":
            result = await extract_content(goal=user_prompt, browser=browser, page_extraction_llm=page_extraction_llm)

        elif action == "final":
            final_output = analysis.get("output", "Final outcome reached")
            return final_output

        else:
            break

        analysis = await gpt_llm.analyze(result)

    return "Scraper finished execution without a final outcome."