import logging
import json
from typing import Dict, Any, List, Optional
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

class MCPPlanner:
    """
    Model Context Protocol (MCP) Planner.
    
    This class implements the MCP for better context management and planning 
    in the AI web scraper. It helps structure the context and maintain 
    state across multiple LLM calls in the scraping process.
    """
    
    def __init__(self, llm: BaseLanguageModel):
        """
        Initialize the MCP Planner.
        
        Args:
            llm: A language model instance that will be used for planning
        """
        self.llm = llm
        self.context = {
            "visited_urls": [],
            "extracted_content": [],
            "search_queries": [],
            "final_answers": []
        }
        self.state = "INITIAL"
        self.max_visited_urls = 15  # Prevent infinite loops
    
    def update_context(self, key: str, value: Any) -> None:
        """
        Update the context with new information.
        
        Args:
            key: The context key to update
            value: The value to add to the context
        """
        if key in self.context:
            if isinstance(self.context[key], list):
                self.context[key].append(value)
            else:
                self.context[key] = value
        else:
            self.context[key] = value
        
        logger.debug(f"Updated context: {key} = {value}")
    
    def add_visited_url(self, url: str) -> None:
        """
        Add a URL to the list of visited URLs.
        
        Args:
            url: The URL that was visited
        """
        if url not in self.context["visited_urls"]:
            self.context["visited_urls"].append(url)
    
    def add_extracted_content(self, url: str, content: Dict[str, Any]) -> None:
        """
        Add extracted content to the context.
        
        Args:
            url: The URL the content was extracted from
            content: The extracted content
        """
        self.context["extracted_content"].append({
            "url": url,
            "content": content
        })
    
    def add_search_query(self, query: str) -> None:
        """
        Add a search query to the context.
        
        Args:
            query: The search query that was performed
        """
        self.context["search_queries"].append(query)
    
    def should_continue_scraping(self) -> bool:
        """
        Determine if scraping should continue based on the context.
        
        Returns:
            bool: True if scraping should continue, False otherwise
        """
        # Check if we've reached a final answer
        if self.context["final_answers"]:
            return False
        
        # Check if we've visited too many URLs
        if len(self.context["visited_urls"]) >= self.max_visited_urls:
            logger.warning(f"Reached maximum URLs ({self.max_visited_urls}), stopping")
            return False
        
        return True
    
    async def decide_next_action(self, user_goal: str, current_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Decide the next action based on the current context and user goal.
        
        Args:
            user_goal: The user's goal for the scraping task
            current_url: The URL currently being processed (if any)
            
        Returns:
            dict: The next action to take
        """
        # Prepare context summary for the LLM
        context_summary = {
            "visited_urls_count": len(self.context["visited_urls"]),
            "visited_urls": self.context["visited_urls"][-5:],  # Last 5 URLs
            "extracted_content_count": len(self.context["extracted_content"]),
            "search_queries": self.context["search_queries"],
            "current_url": current_url,
            "state": self.state
        }
        
        # Add search results information
        search_results = self.context.get("search_results", [])
        if search_results:
            # Only include first 3 results for brevity
            search_results_summary = search_results[:3]
            context_summary["search_results_available"] = len(search_results)
            context_summary["search_results_sample"] = search_results_summary
            
            # Check if we're in a search loop
            search_count = len(self.context.get("search_queries", []))
            if search_count >= 3 and len(self.context.get("visited_urls", [])) == 0:
                context_summary["search_loop_detected"] = True
                logger.warning("Search loop detected - recommend NAVIGATE action")
        else:
            context_summary["search_results_available"] = 0
        
        messages = [
            SystemMessage(content=(
                "You are a web scraping planner. Your job is to decide the next action to take "
                "based on the current context and the user's goal. Consider what information "
                "has been collected so far and what might still be needed.\n\n"
                "Choose one of these actions:\n"
                "1. SEARCH - Only use this when no search has been done yet or current search results aren't relevant\n"
                "2. EXTRACT - Use when on a page that might have relevant information\n"
                "3. NAVIGATE - Use when search results are available but not yet visited (IMPORTANT: prefer this over SEARCH if search_results_available > 0)\n"
                "4. FINISH - Conclude the scraping with a final answer when enough information has been collected\n\n"
                "IMPORTANT GUIDELINES:\n"
                "- If search_results_available > 0, prefer NAVIGATE instead of more SEARCH actions\n"
                "- If search_loop_detected is true, you MUST choose NAVIGATE to break out of the loop\n"
                "- For NAVIGATE, don't include example.com URLs - use actual search results\n"
                "- For SEARCH, only include a 'query' parameter with a specific search query\n"
                "- Keep track of how many searches have been done - never do more than 3 searches before navigating\n\n"
                "Respond with a JSON object containing 'action' and any additional parameters needed."
            )),
            HumanMessage(content=(
                f"User Goal: {user_goal}\n\n"
                f"Current Context: {json.dumps(context_summary, indent=2)}\n\n"
                "What should be the next action? Respond with JSON only."
            ))
        ]
        
        response = await self.llm.ainvoke(input=messages)
        logger.info(f"Raw response: {response.content}")
        try:
            # Clean up the response to handle markdown code blocks
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]  # Remove ```json
            if content.endswith("```"):
                content = content[:-3]  # Remove trailing ```
            
            # Now attempt to parse the JSON
            action_data = json.loads(content.strip())
            logger.info(f"Next action: {action_data}")
            return action_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            # Smart fallback based on context state
            if current_url:
                # If we're on a page, extract content
                return {"action": "EXTRACT"}
            elif self.context.get("search_results") and len(self.context.get("search_results", [])) > 0:
                # If search results are available but no navigation yet, navigate
                return {"action": "NAVIGATE"}
            elif len(self.context.get("visited_urls", [])) > 0 and len(self.context.get("extracted_content", [])) > 0:
                # If we've visited some pages and extracted content, try to finish
                return {"action": "FINISH"}
            else:
                # Default to initial search
                return {"action": "SEARCH", "query": user_goal}
    
    async def generate_final_answer(self, user_goal: str) -> str:
        """
        Generate a final answer based on all collected information.
        
        Args:
            user_goal: The user's original goal
            
        Returns:
            str: The final answer
        """
        # Get the most relevant extracted content
        relevant_content = []
        for item in self.context["extracted_content"]:
            # Only include content that has useful information
            content = item["content"]
            if content.get("action") != "next_url" and content.get("summary"):
                relevant_content.append({
                    "url": item["url"],
                    "summary": content.get("summary", ""),
                    "key_points": content.get("key_points", [])
                })
        
        messages = [
            SystemMessage(content=(
                "You are an expert at synthesizing information from multiple sources. "
                "Based on the information collected during web scraping, provide a "
                "comprehensive answer to the user's original goal. Include citations "
                "to the source URLs when appropriate."
            )),
            HumanMessage(content=(
                f"User Goal: {user_goal}\n\n"
                f"Information Collected:\n{json.dumps(relevant_content, indent=2)}\n\n"
                "Please provide a comprehensive answer based on this information."
            ))
        ]
        
        response = await self.llm.ainvoke(input=messages)
        final_answer = response.content.strip()
        
        # Save to context
        self.context["final_answers"].append(final_answer)
        self.state = "FINISHED"
        
        return final_answer