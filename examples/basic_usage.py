from langchain_openai import ChatOpenAI
from minion_agent.browser import MinionAgent
import asyncio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

async def main():
    # Example 1: Using environment variables for OpenAI configuration
    agent1 = MinionAgent(
        task="Compare the price of GPT-4 and DeepSeek-V3",
        llm=ChatOpenAI(model="gpt-4o"),
        headless=True
    )
    result1 = await agent1.run()
    print("Result 1:", result1)

    # Example 2: Providing custom LLM and configuration
    agent2 = MinionAgent(
        task="Search for the latest news about AI",
        llm=ChatOpenAI(model="gpt-4o"),
        headless=False  # Show browser window
    )
    result2 = await agent2.run()
    print("Result 2:", result2)


if __name__ == "__main__":
    asyncio.run(main()) 