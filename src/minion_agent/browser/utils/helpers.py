import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def save_output(filename: str, content: str) -> str:
    """
    Save output content to a file.
    
    Args:
        filename: The name of the file to save
        content: The content to save
        
    Returns:
        str: Path to the saved file
    """
    try:
        # Create the output directory if it doesn't exist
        os.makedirs("output", exist_ok=True)
        filepath = os.path.join("output", filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Output saved to {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Error saving output to {filename}: {e}")
        return ""

def format_context_for_display(context: Dict[str, Any]) -> str:
    """
    Format MCP context for human-readable display.
    
    Args:
        context: The MCP context dictionary
        
    Returns:
        str: Formatted context for display
    """
    output = []
    
    output.append("# Web Scraping Context Summary")
    output.append("")
    
    # Visited URLs
    output.append("## Visited URLs")
    for i, url in enumerate(context.get("visited_urls", []), 1):
        output.append(f"{i}. {url}")
    output.append("")
    
    # Search Queries
    output.append("## Search Queries")
    for i, query in enumerate(context.get("search_queries", []), 1):
        output.append(f"{i}. {query}")
    output.append("")
    
    # Extracted Content Summary
    output.append("## Extracted Content")
    for i, item in enumerate(context.get("extracted_content", []), 1):
        url = item.get("url", "Unknown URL")
        content = item.get("content", {})
        summary = content.get("summary", "No summary available")
        
        output.append(f"### Source {i}: {url}")
        output.append(summary)
        
        key_points = content.get("key_points", [])
        if key_points:
            output.append("\nKey points:")
            for point in key_points:
                output.append(f"- {point}")
        output.append("")
    
    # Final Answer
    if context.get("final_answers"):
        output.append("## Final Answer")
        output.append(context["final_answers"][-1])
    
    return "\n".join(output)

def truncate_text(text: str, max_length: int = 1000) -> str:
    """
    Truncate text to a maximum length while preserving integrity.
    
    Args:
        text: The text to truncate
        max_length: Maximum length of the truncated text
        
    Returns:
        str: Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    # Try to truncate at a sentence boundary
    truncated = text[:max_length]
    last_period = truncated.rfind('.')
    
    if last_period > max_length * 0.7:  # Only truncate at period if it's not too far back
        return truncated[:last_period + 1] + " [...]"
    else:
        return truncated + " [...]"