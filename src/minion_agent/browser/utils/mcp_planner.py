import logging
import json
from typing import Any, Dict, Optional, List
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

class MCPPlanner:
    """
    Model Context Protocol (MCP) Planner with LLM-guided page interactions.
    """
    def __init__(self, llm: BaseLanguageModel):
        self.llm = llm
        self.context: Dict[str, Any] = {
            "visited_urls": [],
            "extracted_content": [],
            "search_queries": [],
            "final_answers": []
        }
        self.state = "INITIAL"
        self.max_visited_urls = 15

    def add_search_query(self, query: str) -> None:
        self.context["search_queries"].append(query)

    def add_visited_url(self, url: str) -> None:
        if url not in self.context["visited_urls"]:
            self.context["visited_urls"].append(url)

    def add_extracted_content(self, url: str, content: Dict[str, Any]) -> None:
        self.context["extracted_content"].append({"url": url, "content": content})
        logger.info(f"Added extracted content for {url}")

    def should_continue_scraping(self) -> bool:
        if self.context["final_answers"]:
            return False
        if len(self.context["visited_urls"]) >= self.max_visited_urls:
            logger.warning("Reached max visited URLs, stopping")
            return False
        return True

    async def decide_next_action(
        self,
        user_goal: str,
        current_url: Optional[str] = None,
        page_elements: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Decide the next action. When PAGE_INTERACTIONS is chosen, LLM returns
        an `interactions` list of {selector,type,value}.
        The planner receives a snapshot of `page_elements` to choose from.
        """
        # Build context summary
        summary = {
            "visited_urls": self.context.get("visited_urls", [])[-5:],
            "search_queries": self.context.get("search_queries", []),
            "search_results_available": len(self.context.get("search_results", [])),
            "extracted_count": len(self.context.get("extracted_content", [])),
            "current_url": current_url,
            "state": self.state,
            "extracted_content":self.context.get("extracted_content",[]),
            "page_elements": page_elements or []
        }
        search_results = self.context.get("search_results", [])
        if search_results:
            # Only include first 3 results for brevity
            search_results_summary = search_results
            summary["search_results_available"] = len(search_results)
            summary["search_results_sample"] = search_results_summary
            # summary["current_extracted_content"] = 
            
            # Check if we're in a search loop
            search_count = len(self.context.get("search_queries", []))
            if search_count >= 3 and len(self.context.get("visited_urls", [])) == 0:
                summary["search_loop_detected"] = True
                logger.warning("Search loop detected - recommend NAVIGATE action")
        else:
            summary["search_results_available"] = 0
        logger.info(f"extracted content>>> : {summary.get('extracted_content',[])}")

        # Prepare prompt
        messages = [
            SystemMessage(content=(
                "You are a proactive web-scraping planner. Given the context summary below, choose exactly one action: SEARCH, NAVIGATE, EXTRACT, PAGE_INTERACTIONS, or FINISH."
                f"Context Summary:```json {summary}```"
                "Actions:"
                "• SEARCH: Perform a new Google search when no search_results are available or previous results were exhausted. Return `{\"action\":\"SEARCH\",\"query\":\"...\"}`."
                "• NAVIGATE: Visit the next unvisited search_result URL. Return `{\"action\":\"NAVIGATE\",\"url\":\"...\"}`."
                "• EXTRACT: Extract content from the current page without interacting. Return `{\"action\":\"EXTRACT\"}`."
                "• PAGE_INTERACTIONS: Interact with visible page_elements (filters, dropdowns, inputs, links) to reveal or refine content. Use when extract_count > 0 but content incomplete, or extract_count == 0 with available page_elements. Return `{\"action\":\"PAGE_INTERACTIONS\",\"interactions\":[...]}` with precise selectors and types."
                "• FINISH: Stop when extracted_content contains at least one item marked final or with a clear non-empty output that answers the user goal. Return `{\"action\":\"FINISH\"}`."
                "Guidelines:"
                "1. After NAVIGATE, if no EXTRACT has occurred yet, choose EXTRACT."
                "2. If EXTRACT has occurred (extracted_content count > 0) and the result lacks key points or isn’t final, and there are unused page_elements, choose PAGE_INTERACTIONS."
                "3. Only use PAGE_INTERACTIONS when page_elements list is non-empty."
                "4. Use SEARCH only if search_results_available == 0 or all NAVIGATE URLs have been visited."
                "5. Use NAVIGATE if unvisited search_results exist and no EXTRACT or PAGE_INTERACTIONS is currently needed."
                "6. Only FINISH when extracted_content includes at least one item with action \"final\" or a non-empty output answering the goal."
                "7. Always respond with valid JSON containing only the keys: action, and query/url/interactions as required."
            )),
            HumanMessage(content=(
                f"User Goal: {user_goal}"
                "Which action and parameters?"
            ))
        ]
        # Invoke LLM
        response = await self.llm.ainvoke(input=messages)
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = "".join(raw.splitlines()[1:-1])
        try:
            action_data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            action_data = {"action": "EXTRACT"}
        return action_data

    async def generate_final_answer(self, user_goal: str) -> str:
        relevant = [
                {"url": it["url"], "summary": it["content"].get("output", "")}  
                for it in self.context["extracted_content"] if it["content"].get("output")
            ]
        messages = [
            SystemMessage(content=(
                "You are an expert synthesizer. Combine summaries into a final answer.")),
            HumanMessage(content=f"Goal: {user_goal}\nData: {json.dumps(relevant, indent=2)}")
        ]
        resp = await self.llm.ainvoke(input=messages)
        ans = resp.content.strip()
        self.context["final_answers"].append(ans)
        self.state = "FINISHED"
        return ans
