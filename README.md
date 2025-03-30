<!-- Light/Dark Mode Banner Hack -->
<p align="center">
  <img src="static/minion-works-cover-light.png#gh-light-mode-only" alt="Minion Works" width="100%" />
  <img src="static/minion-works-cover-dark.png#gh-dark-mode-only" alt="Minion Works" width="100%" />
</p>

<h1 align="center"> MinionWorks – Modular browser agents that work for bananas 🍌</h1>

<p align="center">
  <em>Modular. Extensible. AI-native browser agents for modern web automation.</em>
</p>

---

## 🚀 Overview

Minion Works is a modular AI agent framework that connects to your browser and executes complex tasks autonomously. Built for developers, researchers, and curious builders.

### ✨ Features
- 🌐 Perform Google searches and scrape content  
- 🤖 Use LLMs (like GPT-4) to plan actions  
- 🔗 Modular architecture for plug-and-play use cases  
- 🔎 DOM interaction & content extraction  
- 🔄 Run workflows via Python or UI  

---

## 🛠️ Installation

1. **Install the package**
   ```bash
   pip install minion-agent
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit your .env file with OpenAI or other API keys
   ```

---

## 🧪 Quick Start

Here’s a complete example using `MinionAgent` with `langchain-openai`:

```python
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
```

---

## 🧠 Example Use Case

```python
agent = MinionAgent(
    task="Find the top 3 ML conferences in 2025 and summarize each.",
    llm=ChatOpenAI(model="gpt-4")
)
await agent.run()
```

---

## 🧪 Testing

```bash
pytest --maxfail=1 --disable-warnings -q
```

Ensure you’re in the root folder where `tests/` lives.

---

## 🤝 Contributing

We welcome PRs, feedback, and creative ideas!  
1. Fork → Branch → Commit  
2. Add tests  
3. Submit a Pull Request  
4. Tell your friends 🚀  

---

## 📖 Citation

```bibtex
@software{minion_works2025,
  author = {Sairaam, Aman, Cheena},
  title = {Minion Works: Let AI take the helm of your browser.},
  year = {2025},
  publisher = {GitHub},
  url = {https://github.com/minionworks/minions}
}
```
