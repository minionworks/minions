import logging
import json
import re
from typing import Dict, Any, List

from langchain_core.language_models.base import BaseLanguageModel

logger = logging.getLogger(__name__)

class OpenAIPageExtractionLLM:
    """
    A wrapper for OpenAI models that extracts information from web pages in full,
    handling arbitrarily large content by chunking and then uses an LLM call
    to decide finality based on the merged output.
    """
    MAX_CHUNK_CHARS = 15000  # tweak to fit your token limits

    def __init__(self, llm: BaseLanguageModel):
        self.llm = llm

    async def extract_with_function_call(self, content: str, goal: str) -> Dict[str, Any]:
        # 1) chunk the page
        chunks = self._chunk_content(content)
        partials: List[Dict[str, Any]] = []
        for idx, chunk in enumerate(chunks, start=1):
            logger.info(f"Processing chunk {idx}/{len(chunks)} (len={len(chunk)})")
            partials.append(await self._extract_chunk(chunk, goal))

        # 2) merge them
        merged = self._merge_partials(partials)

        # 3) decide finality with a fresh LLM call
        merged["action"] = await self._decide_action(merged["output"], goal)
        return merged

    def _chunk_content(self, content: str) -> List[str]:
        if len(content) <= self.MAX_CHUNK_CHARS:
            return [content]
        return [
            content[i : i + self.MAX_CHUNK_CHARS]
            for i in range(0, len(content), self.MAX_CHUNK_CHARS)
        ]

    async def _extract_chunk(self, chunk: str, goal: str) -> Dict[str, Any]:
        functions = [{
            "name": "extract_content",
            "description": "Extract relevant content from a webpage",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["final", "next_url"],
                        "description": "Does this chunk answer the question?"
                    },
                    "summary": {"type": "string"},
                    "key_points": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "context": {"type": "string"},
                    "output": {"type": "string"}
                },
                "required": ["action", "summary", "key_points", "output"]
            }
        }]

        messages = [
            {"role": "system", "content": (
                "You are analyzing a web page to extract relevant information. "
                "If this chunk fully answers the user’s goal, return 'action':'final'. "
                "Otherwise 'next_url'."
            )},
            {"role": "user", "content": f"Question: {goal}\n\nPage Content:\n{chunk}"}
        ]

        response = await self.llm.ainvoke(
            input=messages,
            functions=functions,
            function_call={"name": "extract_content"},
        )
        return self._parse_function_response(response)

    async def _decide_action(self, merged_output: str, goal: str) -> str:
        """
        One-shot LLM call to decide if the merged_output fully satisfies the goal.
        Returns 'final' or 'next_url'.
        """
        functions = [{
            "name": "decide_action",
            "description": "Decide whether the provided answer fully addresses the goal",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["final", "next_url"],
                        "description": "final if it answers, next_url otherwise"
                    }
                },
                "required": ["action"]
            }
        }]

        messages = [
            {"role": "system", "content": (
                "You are determining if a proposed answer fully addresses the user’s question."
            )},
            {"role": "user", "content": (
                f"Goal: {goal}\n\n"
                f"Proposed Answer:\n{merged_output}"
            )}
        ]

        response = await self.llm.ainvoke(
            input=messages,
            functions=functions,
            function_call={"name": "decide_action"},
            # you could set temperature=0 here for determinism
        )

        # extract the JSON arguments
        return self._parse_function_response(response)

    def _parse_function_response(self, response: Any) -> Dict[str, Any]:
        # (same as before) tries dict, response.function_call, additional_kwargs, embedded JSON
        if isinstance(response, dict) and "action" in response:
            return response

        fc = getattr(response, "function_call", None)
        if fc and hasattr(fc, "arguments"):
            # logger.info(f"Inside Arguments: {fc}")
            return self._load_json(fc.arguments)

        ak = getattr(response, "additional_kwargs", {})
        if isinstance(ak, dict) and "function_call" in ak:
            # logger.info(f"Inside function_call: {ak["function_call"]["arguments"]}")

            return self._load_json(ak["function_call"]["arguments"])

        text = getattr(response, "content", None) or str(response)
        # logger.info(f"Inside text: {text}")
        
        m = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
        if m:
            return self._load_json(m.group(1))
        return self._load_json(text)

    def _load_json(self, maybe_json: str) -> Dict[str, Any]:
        s = maybe_json.strip()
        # logger.info(f"ss>>>>>>: {maybe_json}")
        if s.startswith("```"):
            s = s.strip("```")
        try:
            return json.loads(s)
        except Exception as e:
            logger.error(f"JSON parse error: {e}\n{s[:200]}")
            return {"action": "next_url", "summary": "", "key_points": [], "context": "", "output": ""}

    def _merge_partials(self, parts: List[Dict[str, Any]]) -> Dict[str, Any]:
        merged = {
            "action": "next_url",
            "summary": "",
            "key_points": [],
            "context": "",
            "output": ""
        }
        for part in parts:
            merged["summary"] += part.get("summary", "") + "\n"
            merged["key_points"].extend(part.get("key_points", []))
            merged["context"] += part.get("context", "") + "\n"
            merged["output"] += part.get("output", "") + "\n"

        merged["key_points"] = list(dict.fromkeys(merged["key_points"]))
        return merged
