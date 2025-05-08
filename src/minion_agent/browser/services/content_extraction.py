import logging
import markdownify
import re
import tempfile
import os
from urllib.parse import urlparse
from pypdf import PdfReader
import asyncio
import subprocess
import io
from typing import Dict, Any, List, Optional
import requests
from io import BytesIO

logger = logging.getLogger(__name__)

async def extract_pdf_content(browser, url: str) -> str:
    """
    Extract text content from a PDF file.
    Uses a combination of browser PDF.js extraction and downloading + external tools if available.
    
    Args:
        browser: Browser wrapper instance
        url: URL of the PDF document
    
    Returns:
        str: Extracted text content from the PDF
    """
    logger.info(f"Attempting to extract content from PDF at {url}")
    page = await browser.get_current_page()
    
    # Method 1: Try to extract text directly from browser if PDF.js is used
    try:
        # Check if PDF.js is being used to display the PDF
        pdf_text = await page.evaluate('''() => {
            // Check for PDF.js viewer
            if (typeof PDFViewerApplication !== 'undefined') {
                const pdfDoc = PDFViewerApplication.pdfDocument;
                if (pdfDoc) {
                    return (async () => {
                        let text = "";
                        for (let i = 1; i <= pdfDoc.numPages; i++) {
                            const page = await pdfDoc.getPage(i);
                            const content = await page.getTextContent();
                            text += content.items.map(item => item.str).join(" ") + "\\n\\n";
                        }
                        return text;
                    })();
                }
            }
            return null;
        }''')
        
        if pdf_text:
            logger.info("Successfully extracted PDF text using PDF.js")
            return pdf_text
    except Exception as e:
        logger.warning(f"Error extracting PDF text from viewer: {e}")
    
    # Method 2: Try to download the PDF and extract text with text extraction tools
    try:
        # Create a temporary file for the PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            pdf_path = temp_file.name
        
        # Download the PDF
        logger.info(f"Downloading PDF from {url}")
        
        # Use browser's download capabilities
        download_script = f'''
        async () => {{
            const response = await fetch("{url}");
            const blob = await response.blob();
            const buffer = await blob.arrayBuffer();
            
            // Convert ArrayBuffer to Base64
            const base64 = btoa(
                new Uint8Array(buffer).reduce(
                    (data, byte) => data + String.fromCharCode(byte), ''
                )
            );
            
            return base64;
        }}
        '''
        
        try:
            pdf_base64 = await page.evaluate(download_script)
            
            if pdf_base64:
                # Decode base64 and write to file
                with open(pdf_path, 'wb') as f:
                    f.write(io.BytesIO(bytes(pdf_base64, encoding='utf-8')).getvalue())
                    
                logger.info(f"PDF downloaded to {pdf_path}")
            else:
                logger.warning("Failed to download PDF content")
                return ""
                
        except Exception as e:
            logger.warning(f"Error downloading PDF: {e}")
            return ""
        
        # Extract text using pdftotext if available
        try:
            logger.info("Attempting PDF text extraction with external tool")
            result = subprocess.run(
                ["pdftotext", pdf_path, "-"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout:
                logger.info("Successfully extracted PDF text with pdftotext")
                return result.stdout
                
            logger.warning(f"pdftotext extraction failed: {result.stderr}")
        except FileNotFoundError:
            logger.warning("pdftotext not available on the system")
        except Exception as e:
            logger.warning(f"Error in PDF extraction: {e}")
        finally:
            # Clean up the temporary file
            try:
                os.unlink(pdf_path)
            except:
                pass
    
    except Exception as e:
        logger.error(f"Overall error in PDF extraction: {e}")
    
    logger.warning("All PDF extraction methods failed")
    return ""

async def process_extracted_content(content: str, title: str, url: str, goal: str, page_extraction_llm) -> Dict[str, Any]:
    """
    Process extracted content using the LLM.
    
    Args:
        content: The extracted text content
        title: Page title
        url: Page URL
        goal: User's search goal
        page_extraction_llm: LLM instance for extraction
        
    Returns:
        Dict[str, Any]: Extraction result with action, summary, etc.
    """
    # Add page metadata to help with content assessment
    page_metadata = f"""
    URL: {url}
    TITLE: {title}
    
    CONTENT:
    """
    
    content_with_metadata = page_metadata + content
    
    # Extract with function call
    extraction_result = await page_extraction_llm.extract_with_function_call(content_with_metadata, goal)
    
    # Enhance the extraction result with a relevance score
    summary = extraction_result.get("summary", "")
    key_points = extraction_result.get("key_points", [])
    
    # Calculate a relevance score
    relevance_score = 0
    if extraction_result.get("action") == "final":
        relevance_score = 1.0  # Highest relevance if this is the final answer
    elif summary and len(key_points) > 2:
        # More key points suggests more relevant content was found
        relevance_score = min(0.9, 0.3 + (len(key_points) * 0.1))
    elif summary:
        relevance_score = 0.3  # Some content but not much
    
    # Add the score to the result
    extraction_result["relevance_score"] = relevance_score
    extraction_result["page_url"] = url
    extraction_result["page_title"] = title
    
    return extraction_result


async def extract_content(goal: str,
                          browser,
                          page_extraction_llm,
                          target_selector: str = "") -> dict:
    """
    Extract page content (HTML or PDF), or if it’s a form, extract form fields,
    then call the LLM to answer the goal.
    Returns a dict with {action, summary, key_points, context, output, relevance_score}.
    """
    page = await browser.get_current_page()
    # ---- FIXED: page.url is a string property, not a coroutine ----
    url = page.url
    title = await page.title()

    # --- 1) PDF handling via PyPDF2 ------------------
    is_pdf = (
        url.lower().endswith('.pdf') or
        '/pdf/' in url.lower() or
        'type=pdf' in url.lower()
    )
    if not is_pdf:
        try:
            content_type = await page.evaluate("() => document.contentType || ''")
            if 'pdf' in content_type.lower():
                is_pdf = True
        except Exception:
            pass

    if is_pdf:
        logger.info(f"Detected PDF at {url}, fetching and extracting text…")
        resp = requests.get(url)
        reader = PdfReader(BytesIO(resp.content))
        pdf_text = ""
        for p in reader.pages:
            text = p.extract_text() or ""
            pdf_text += text + "\n"
        return await process_extracted_content(pdf_text, title, url, goal, page_extraction_llm)

    # # --- 2) Form-element extraction ------------------
    # form_elems = await page.query_selector_all("input, textarea, select")
    # if form_elems:
    #     logger.info("Page contains form elements — extracting schema")
    #     fields = []
    #     radio_groups = {}

    #     for elem in form_elems:
    #         tag = await elem.evaluate("e => e.tagName")
    #         name = (await elem.get_attribute("name")) or (await elem.get_attribute("id")) or ""
    #         ftype = ""
    #         placeholder = ""
    #         options = []

    #         if tag == "INPUT":
    #             ftype = (await elem.get_attribute("type")) or "text"
    #             placeholder = await elem.get_attribute("placeholder") or ""
    #             if ftype == "radio" and name:
    #                 val = (await elem.get_attribute("value")) or ""
    #                 radio_groups.setdefault(name, []).append(val)
    #                 continue

    #         elif tag == "TEXTAREA":
    #             ftype = "textarea"
    #             placeholder = await elem.get_attribute("placeholder") or ""

    #         elif tag == "SELECT":
    #             ftype = "select"
    #             options = await elem.evaluate(
    #                 "e => Array.from(e.options).map(o => o.value || o.text)"
    #             )

    #         fields.append({
    #             "label": name,
    #             "type": ftype,
    #             "placeholder": placeholder,
    #             "options": options
    #         })

    #     for name, opts in radio_groups.items():
    #         fields.append({
    #             "label": name,
    #             "type": "radio",
    #             "placeholder": "",
    #             "options": opts
    #         })

    #     md = "\n".join(
    #         f"- **{f['label']}** ({f['type']})"
    #         + (f": placeholder='{f['placeholder']}'" if f['placeholder'] else "")
    #         + (f", options={f['options']}" if f['options'] else "")
    #         for f in fields
    #     )
    #     content_markdown = f"# Form Fields\n{md}"
    #     return await process_extracted_content(content_markdown, title, url, goal, page_extraction_llm)

    # # --- 3) Standard HTML extraction ------------------
    # common_selectors = ["div#main", "main", "div.main", "div#content", "div.content"]
    # selectors = [target_selector] + common_selectors if target_selector.strip() else common_selectors

    content_html = ""
    # for sel in selectors:
    #     if not sel:
    #         continue
    #     try:
    #         await page.wait_for_selector(sel, timeout=3000)
    #         el = await page.query_selector(sel)
    #         if el:
    #             content_html = await el.inner_html()
    #             logger.info(f"✔️ Found content with selector '{sel}'")
    #             break
    #     except Exception as e:
    #         logger.debug(f"Selector '{sel}' failed: {e}")

    if not content_html:
        logger.warning("No selector matched; grabbing full page HTML")
        content_html = await page.content()

    content_markdown = markdownify.markdownify(content_html)
    return await process_extracted_content(content_markdown, title, url, goal, page_extraction_llm)
