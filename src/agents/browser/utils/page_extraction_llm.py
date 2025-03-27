import json
import logging
import markdownify
from openai import AsyncOpenAI

from src.config.settings import OPENAI_API_KEY
aclient = AsyncOpenAI(api_key=OPENAI_API_KEY)

logger = logging.getLogger(__name__)

# Function calling schema for extraction
extraction_function = {
    "name": "extract_content_result",
    "description": (
        "Analyze the page content to see if it answers the question. "
        "If yes, return action='final' with a summary, key_points, context, and output. "
        "If not, return action='next_url'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["final", "next_url"],
                "description": "If 'final', the page answers the question. If 'next_url', it does not."
            },
            "summary": {
                "type": "string",
                "description": "Detailed answer if the page answers the question, otherwise empty."
            },
            "key_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of bullet points or highlights from the page."
            },
            "context": {
                "type": "string",
                "description": "Additional context or disclaimers."
            },
            "output": {
                "type": "string",
                "description": "If action='final', the final text to display."
            }
        },
        "required": ["action"]
    }
}

class OpenAIPageExtractionLLM:
    """
    Uses OpenAI's ChatCompletion with function calling to extract 
    content from the page in a guaranteed JSON format.
    """
    async def extract_with_function_call(self, page_content_markdown: str, question: str) -> dict:
        system_message = {
            "role": "system",
            "content": (
                "You are a specialized page extraction assistant. "
                "Analyze the provided page content to see if it answers the user's question. "
                "If yes, call the function 'extract_content_result' with action='final', summary, key_points, context, and output. "
                "If not, call the function 'extract_content_result' with action='next_url'. "
                "Do not return anything else."
            )
        }
        user_message = {
            "role": "user",
            "content": f"Question: {question}\nPage content:\n{page_content_markdown}"
        }
        response = await aclient.chat.completions.create(model="gpt-4o",
        messages=[system_message, user_message],
        functions=[extraction_function],
        function_call="auto",
        temperature=0.0)
        choice = response.choices[0]
        finish_reason = choice.finish_reason

        if finish_reason == "function_call":
            function_name = choice.message.function_call.name
            arguments_str = choice.message.function_call.arguments
            try:
                arguments = json.loads(arguments_str)
                logger.info(f"Function '{function_name}' called with arguments: {arguments}")
                return arguments
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing function call arguments: {arguments_str}")
                return {"action": "next_url", "summary": "", "key_points": [], "context": "", "output": ""}
        else:
            logger.warning("Model did not call the function. Returning next_url.")
            return {"action": "next_url", "summary": "", "key_points": [], "context": "", "output": ""}
