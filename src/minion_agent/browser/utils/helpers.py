import logging

logger = logging.getLogger(__name__)

def save_output(filename: str, content: str) -> None:
    """
    Save content to a file.
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Output saved to {filename}")
    except Exception as e:
        logger.error(f"Error saving output: {e}")
