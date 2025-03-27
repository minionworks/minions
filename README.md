# Minions

This project is a modular web scraper built using Python, Playwright, and OpenAI's GPT. It is designed to perform web scraping tasks efficiently by orchestrating various services and utilizing AI for decision-making.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)
- [Citation](#Citation)
- [Project Structure](#project-structure)

## Features

- Performs Google searches and extracts relevant URLs and titles.
- Navigates to specified URLs and extracts content.
- Uses OpenAI's GPT for analyzing outputs and deciding next actions.
- Modular structure for easy maintenance and extensibility.


---

## Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/yourusername/minions.git
   cd minions
   ```

2. **Create and Activate a Virtual Environment:**
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set Up Environment Variables:**
   - Copy `.env.example` to `.env` and set your OpenAI API key:
     ```bash
     cp .env.example .env
     ```
   - Edit the `.env` file:
     ```
     OPENAI_API_KEY=your_openai_api_key_here
     ```

## Usage

### Running the Application

Run the main entry point from the project root:

```bash
cd minions
python -m src.agents.browser.main
```

Or, you can run it directly by setting the PYTHONPATH:

```bash
# From the project root:
$env:PYTHONPATH = "C:\path\to\minions"  # (PowerShell on Windows)
python -m src.agents.browser.main
```

### Example Notebook

An example Jupyter Notebook demonstrating how to run the scraper is available in:
```
examples/browser-minion/sample_example.ipynb
```
Open the notebook with Jupyter Lab or Notebook:
```bash
jupyter notebook examples/browser-minion/sample_example.ipynb
```

## Testing

Tests are written using pytest and pytest‑asyncio. To run the tests, simply run:

```bash
pytest --maxfail=1 --disable-warnings -q
```

Ensure you are in the project root (where `tests/` is located).

## Contributing

Contributions are welcome! Please follow these steps:
1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Write tests for your changes.
4. Open a pull request describing your changes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.


## Citation

If you use Minion Works in your research or project, please cite:

```bibtex
@software{minion_works2025,
  author = {Sairaam,Aman,Cheena},
  title = {Minion Works: Let AI take the helm of your browser.},
  year = {2025},
  publisher = {GitHub},
  url = {https://github.com/minionworks/minions}
}
```

## Project Structure
```
minions/
├── .env.example
├── LICENSE
├── README.md
├── requirements.txt
├── setup.py
├── test.py
├── examples/
│   └── browser-minion/
│       └── sample_example.ipynb
├── src/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── agents/
│   │   └── api/
│   │       └── llm.py
│   ├── browser/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── planner/
│   │   │   └── openai_gpt.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── content_extraction.py
│   │   │   ├── google_search.py
│   │   │   ├── navigation.py
│   │   │   └── orchestrator.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── browser_wrapper.py
│   │       ├── helpers.py
│   │       └── page_extraction_llm.py
└── tests/
    ├── __init__.py
    ├── test_content_extraction.py
    ├── test_google_search.py
    ├── test_navigation.py
    └── test_orchestrator.py
    
```

