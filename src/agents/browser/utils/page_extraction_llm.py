import json
import logging
import markdownify
from typing import Dict, Any
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

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
    A class that uses OpenAI's function calling to extract and analyze content from web pages.
    
    This class takes a language model instance and provides methods to analyze page content
    and determine if it contains the answer to a given question.
    """

    def __init__(self, llm: BaseLanguageModel):
        """
        Initialize the extraction LLM.
        
        Args:
            llm: A language model instance that supports function calling
        """
        self.llm = llm

    async def extract_with_function_call(self, page_content_markdown: str, question: str) -> Dict[str, Any]:
        """
        Analyze page content to determine if it answers the given question.
        
        Args:
            page_content_markdown: The page content in markdown format
            question: The question to check if the page answers
            
        Returns:
            Dict containing the analysis result with keys:
            - action: Either 'final' or 'next_url'
            - summary: Detailed answer if found
            - key_points: List of important points
            - context: Additional context
            - output: Final formatted output
        """
        messages = [
            SystemMessage(content=(
                "You are a specialized page extraction assistant. "
                "Analyze the provided page content to see if it answers the user's question. "
                "If yes, call the function 'extract_content_result' with action='final', summary, key_points, context, and output. "
                "If not, call the function 'extract_content_result' with action='next_url'. "
                "Do not return anything else."
            )),
            HumanMessage(content=f"Question: {question}\nPage content:\n{page_content_markdown}")
        ]

        try:
            response = await self.llm.ainvoke(input=messages,functions=[extraction_function])

            if isinstance(response, AIMessage) and hasattr(response, 'additional_kwargs'):
                function_call = response.additional_kwargs.get('function_call')
                if function_call:
                    arguments_str = function_call.get("arguments", "{}")
                    try:
                        arguments = json.loads(arguments_str)
                        logger.info(f"Function '{function_call['name']}' called with arguments: {arguments}")
                        return arguments
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing function call arguments: {e}")
                        return self._get_fallback_response()
            
            logger.warning("Model did not call a function. Returning fallback.")
            return self._get_fallback_response()
            
        except Exception as e:
            logger.error(f"Error during content extraction: {e}")
            return self._get_fallback_response()

    def _get_fallback_response(self) -> Dict[str, Any]:
        """Return a fallback response when extraction fails."""
        return {
            "action": "next_url",
            "summary": "",
            "key_points": [],
            "context": "",
            "output": ""
        }