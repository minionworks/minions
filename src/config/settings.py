from dotenv import load_dotenv
load_dotenv()

import os

class Settings:
    """
    Configuration settings for the web scraper application.
    """
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your_openai_api_key_here")
    GOOGLE_SEARCH_URL = "https://www.google.com/search?q={query}&udm=14"
    DEFAULT_WAIT_TIME = 3
    MAX_SEARCH_RESULTS = 10
    HEADLESS_MODE = False  # Set to True for headless browser operation

    @staticmethod
    def get_browser_args():
        return [
            '--no-sandbox',
            '--disable-blink-features=AutomationControlled',
            '--disable-infobars',
            '--disable-background-timer-throttling',
            '--disable-popup-blocking',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-window-activation',
            '--disable-focus-on-load',
            '--no-first-run',
            '--no-default-browser-check',
            '--no-startup-window',
            '--window-position=0,0',
        ]