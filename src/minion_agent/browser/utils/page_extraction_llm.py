import logging
import json
from typing import Dict, Any, List
from langchain_core.language_models.base import BaseLanguageModel

logger = logging.getLogger(__name__)

class OpenAIPageExtractionLLM:
    """
    A wrapper for OpenAI models that extracts information from web pages.
    Uses function calls to structure the output in a consistent format.
    """
    
    def __init__(self, llm: BaseLanguageModel):
        """
        Initialize the page extraction LLM.
        
        Args:
            llm: A language model instance
        """
        self.llm = llm
    
    async def extract_with_function_call(self, content: str, goal: str) -> Dict[str, Any]:
        """
        Extract information from content using function calls to structure the output.
        
        Args:
            content: The page content (in markdown)
            goal: The user's goal or query
            
        Returns:
            dict: The structured extraction result
        """
        try:
            # Use LangChain to invoke the model with function calling
            messages = [
                {"role": "system", "content": (
                    "You are analyzing a web page to extract relevant information. "
                    "Based on the content, determine whether it answers the user's question. "
                    "If it does, create a summary and extract key points."
                )},
                {"role": "user", "content": (
                    f"Question: {goal}\n\n"
                    f"Page Content:\n{content[:10000]}"  # Truncate to avoid token limits
                )}
            ]
            
            # Define the function schema for structured output
            functions = [
                {
                    "name": "extract_content",
                    "description": "Extract relevant content from a webpage",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["final", "next_url"],
                                "description": "Whether this content answers the question (final) or not (next_url)"
                            },
                            "summary": {
                                "type": "string",
                                "description": "A brief summary of the content's relevance to the query"
                            },
                            "key_points": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of key points extracted from the content"
                            },
                            "context": {
                                "type": "string",
                                "description": "Additional context or notes about the content"
                            },
                            "output": {
                                "type": "string",
                                "description": "The final output answer if action is 'final'"
                            }
                        },
                        "required": ["action", "summary", "key_points", "output"]
                    }
                }
            ]
            
            # Convert to LangChain format
            langchain_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    langchain_messages.append({"role": "system", "content": msg["content"]})
                else:
                    langchain_messages.append({"role": "user", "content": msg["content"]})
            
            response = await self.llm.ainvoke(
                input=langchain_messages,
                functions=functions,
                function_call={"name": "extract_content"}
            )
            
            # Parse the response
            logger.info(f"Raw extraction response type: {type(response)}")
            
            # Try different approaches to extract the function call results
            try:
                # First method: Check if it's a direct dictionary response
                if isinstance(response, dict) and "action" in response:
                    logger.info("Found direct dictionary response")
                    return response
                
                # Second method: OpenAI-style function call 
                function_call = getattr(response, "function_call", None)
                if function_call and hasattr(function_call, "arguments"):
                    logger.info("Found OpenAI-style function call")
                    arguments = function_call.arguments
                    
                    # Clean up potential markdown or formatting
                    if isinstance(arguments, str):
                        if arguments.startswith("```json"):
                            arguments = arguments[7:]
                        if arguments.endswith("```"):
                            arguments = arguments[:-3]
                        arguments = arguments.strip()
                    
                    extraction_result = json.loads(arguments)
                    logger.info(f"Extraction result action: {extraction_result.get('action')}")
                    return extraction_result
                
                # Third method: Look for a content attribute (common in some LangChain responses)
                content = getattr(response, "content", None)
                if content:
                    logger.info("Found content attribute, attempting to parse")
                    # Try to extract JSON from the content
                    import re
                    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                        extraction_result = json.loads(json_str)
                        logger.info(f"Extracted JSON from content: {extraction_result.get('action')}")
                        return extraction_result
                    
                    # If we still can't find JSON, try one more approach
                    try:
                        # Maybe it's a direct JSON string without markdown formatting
                        extraction_result = json.loads(content)
                        if "action" in extraction_result:
                            logger.info("Parsed direct JSON from content")
                            return extraction_result
                    except json.JSONDecodeError:
                        pass
                
                # Fourth method: Look for .additional_kwargs.function_call
                additional_kwargs = getattr(response, "additional_kwargs", {})
                if additional_kwargs and "function_call" in additional_kwargs:
                    logger.info("Found function_call in additional_kwargs")
                    fc = additional_kwargs["function_call"]
                    if isinstance(fc, dict) and "arguments" in fc:
                        args = fc["arguments"]
                        extraction_result = json.loads(args)
                        logger.info(f"Extracted from additional_kwargs: {extraction_result.get('action')}")
                        return extraction_result
                
                # Last resort: If the response itself is a string, try parsing it
                if isinstance(response, str):
                    logger.info("Response is a string, attempting to parse")
                    # Try to find JSON in the string
                    import re
                    json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                        extraction_result = json.loads(json_str)
                        return extraction_result
                    
                    # Maybe it's direct JSON without markdown
                    try:
                        extraction_result = json.loads(response)
                        if "action" in extraction_result:
                            return extraction_result
                    except json.JSONDecodeError:
                        pass
                
                # Log the full response for debugging
                logger.error(f"Unable to parse response: {str(response)[:500]}...")
                
            except Exception as e:
                logger.error(f"Error parsing extraction response: {e}")
            
            # Fallback in case all parsing methods fail
            logger.warning("Function call failed, using fallback parsing")
            return {
                "action": "next_url",
                "summary": "",
                "key_points": [],
                "context": "",
                "output": ""
            }
        
        except Exception as e:
            logger.error(f"Error in extract_with_function_call: {e}")
            return {
                "action": "next_url",
                "summary": "",
                "key_points": [],
                "context": "",
                "output": f"Error: {str(e)}"
            }