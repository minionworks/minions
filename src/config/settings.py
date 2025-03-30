# src/config/settings.py
import os
from dotenv import load_dotenv

load_dotenv(verbose=True, override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
