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

1. **Clone the repo**
   ```bash
   git clone https://github.com/minionworks/minions.git
   cd minions
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit your .env file with OpenAI or other API keys
   ```

---

## 🧪 Quick Start

```bash
python -m src.minion_agent.browser.main
```

Or run with PYTHONPATH if you’re outside the root:

```powershell
$env:PYTHONPATH = "C:\path\to\minions"
python -m src.minion_agent.browser.main
```

---

## 🧠 Example Use Case

```python
agent = BrowserMinion(
    task="Find the top 3 ML conferences in 2025 and summarize each.",
    model="gpt-4"
)
agent.run()
```

Or check out this Notebook Example.

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

---
