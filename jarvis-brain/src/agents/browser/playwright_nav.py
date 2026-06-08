from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import markdownify
from src.core.logger import logger

def browse_web(url: str) -> str:
    """
    Navigates to a URL, bypasses basic static scraping blocks via a real Chromium engine,
    strips the DOM of noise, and returns clean Markdown.
    """
    logger.info("browser_agent_navigating", url=url)
    
    html_content = ""
    try:
        # Use synchronous playwright for stability inside our blocking Redis worker
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # wait_until="networkidle" ensures JavaScript frameworks finish rendering
            page.goto(url, wait_until="networkidle", timeout=15000)
            html_content = page.content()
            browser.close()
            
    except Exception as e:
        logger.error("browser_navigation_failed", url=url, error=str(e))
        return f"Error: Failed to navigate to {url}. Details: {str(e)}"

    # --- Phase 2: HTML Sanitization ---
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Violently destroy non-content tags to save LLM tokens
        for tag in soup(["script", "style", "noscript", "iframe", "svg", "nav", "footer"]):
            tag.extract()
            
        # Convert the remaining DOM to Markdown
        markdown_text = markdownify.markdownify(str(soup), heading_style="ATX")
        
        # Strip excessive blank lines and whitespace
        clean_md = "\n".join([line.strip() for line in markdown_text.splitlines() if line.strip()])
        
        # Hard cap at 10,000 characters to protect the LLM context window limits
        return clean_md[:10000]
        
    except Exception as e:
        logger.error("html_parsing_failed", error=str(e))
        return f"Error: Failed to parse the website content."