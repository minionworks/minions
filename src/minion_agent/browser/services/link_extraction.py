import logging
from typing import List

logger = logging.getLogger(__name__)

async def extract_page_links(browser) -> List[str]:
    """
    Extract all links from the current page.
    
    Args:
        browser: The browser wrapper instance
        
    Returns:
        List[str]: List of URLs found on the page
    """
    page = await browser.get_current_page()
    
    try:
        # First try to click "Accept cookies" button if it exists to access more content
        try:
            accept_buttons = await page.query_selector_all(
                'button:has-text("Accept"), button:has-text("OK"), '
                'button:has-text("cookies"), button:has-text("Accept All"), '
                'button:has-text("I agree"), button:has-text("Continue"), '
                'button:has-text("Consent")'
            )
            if accept_buttons:
                logger.info("Found cookie consent button, attempting to click it")
                await accept_buttons[0].click()
        except Exception as e:
            logger.debug(f"No cookie button found or error clicking it: {e}")
        
        # Extract all links via JavaScript execution for better coverage
        links = await page.evaluate('''
            () => {
                const anchors = Array.from(document.querySelectorAll('a'));
                const validLinks = [];
                
                for (const anchor of anchors) {
                    const href = anchor.href;
                    if (href && href.startsWith('http') && !href.includes('#')) {
                        validLinks.push(href);
                    }
                }
                
                return validLinks;
            }
        ''')
        
        # Ensure the links list contains only strings and remove duplicates
        unique_links = list(set([str(link) for link in links if link]))
        
        # Limit the number of links to prevent overwhelming the system
        if len(unique_links) > 20:
            logger.info(f"Found {len(unique_links)} links, limiting to first 20")
            unique_links = unique_links[:20]
        
        logger.info(f"Extracted {len(unique_links)} unique links from page")
        return unique_links
    
    except Exception as e:
        logger.error(f"Error extracting links: {e}")
        return []

def filter_links_by_relevance(links: List[str], current_domain: str, keywords: List[str]) -> List[str]:
    """
    Filter and sort links by their potential relevance to the search query.
    
    Args:
        links: List of URLs to filter
        current_domain: The current domain we're on
        keywords: Keywords to prioritize links by
        
    Returns:
        List[str]: Filtered and sorted list of URLs
    """
    # First, separate links by domain (same domain vs different domains)
    same_domain_links = []
    different_domain_links = []
    
    for link in links:
        if current_domain in link:
            same_domain_links.append(link)
        else:
            different_domain_links.append(link)
    
    # Function to score a link based on keywords presence
    def score_link(link):
        link_lower = link.lower()
        # Higher score if keywords appear in the URL
        return sum(2 if keyword.lower() in link_lower else 0 for keyword in keywords)
    
    # Sort links within each category by relevance score
    same_domain_links.sort(key=score_link, reverse=True)
    different_domain_links.sort(key=score_link, reverse=True)
    
    # Prioritize same-domain links, but include some cross-domain links
    # if they seem highly relevant
    result = same_domain_links
    
    # Add high-scoring different-domain links if they have keywords
    relevant_external = [
        link for link in different_domain_links
        if score_link(link) > 0
    ][:5]  # Limit to top 5
    
    result.extend(relevant_external)
    return result