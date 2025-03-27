import asyncio

async def wait(seconds: int = 3):
    """
    Waits for a given number of seconds.
    """
    msg = f'🕒  Waiting for {seconds} seconds'
    print("wait msg:", msg)
    await asyncio.sleep(seconds)
    return msg

def format_prompt(goal: str, content: str) -> str:
    """
    Formats the prompt for the OpenAI API based on the extraction goal and page content.
    """
    return (
        "Your task is to extract the content of the page. You will be given a page "
        "and a goal and you should extract all relevant information around this goal from the page. "
        "If the goal is vague, summarize the page. Respond in JSON format. "
        "Extraction goal: {goal}, Page: {page}"
    ).format(goal=goal, page=content)