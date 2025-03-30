import json
import logging
from openai import AsyncOpenAI
from src.config.settings import OPENAI_API_KEY
aclient = AsyncOpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Optionally, if you prefer the AsyncOpenAI client:
# from openai import AsyncOpenAI
# openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

class OpenAIGPT:
    """
    Uses OpenAI's ChatCompletion to decide the next action.
    """
    async def analyze(self, input_text: str) -> dict:
        system_message = (
            "You are a web scraper controller. Based on the provided page content, decide the next action using one of these JSON formats:\n"
            '  {"action": "go_to_url", "url": "https://example.com"}\n'
            '  {"action": "next_url"}\n'
            '  {"action": "wait", "seconds": 3}\n'
            '  {"action": "extract_content"}\n'
            '  {"action": "search_next_page"}\n'
            '  {"action": "final", "output": "Final answer text..."}\n'
            "If the page does not answer the question, respond with {\"action\": \"next_url\"}.\n"
            "Do not include extra text."
        )
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Input: {input_text}"}
        ]
        response = await aclient.chat.completions.create(model="gpt-4o",
        messages=messages,
        temperature=0.0)
        raw_response = response.choices[0].message.content.strip()
        try:
            return json.loads(raw_response)
        except Exception as e:
            logger.error(f"GPT parse error: {raw_response}")
            return {"action": "final", "output": f"GPT parse error: {raw_response}"}
