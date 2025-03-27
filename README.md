# Minions

This project is a modular web scraper built using Python, Playwright, and OpenAI's GPT. It is designed to perform web scraping tasks efficiently by orchestrating various services and utilizing AI for decision-making.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

## Features

- Performs Google searches and extracts relevant URLs and titles.
- Navigates to specified URLs and extracts content.
- Uses OpenAI's GPT for analyzing outputs and deciding next actions.
- Modular structure for easy maintenance and extensibility.

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/minions/minions.git
   cd minions
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables by copying `.env.example` to `.env` and filling in the required values.

## Usage

To run the web scraper, execute the following command:
```
python src/main.py
```

You can modify the `user_prompt` variable in `src/main.py` to change the query for the web scraper.

## Configuration

Configuration settings, such as API keys, can be found in `src/config/settings.py`. Make sure to update these settings according to your environment.

## Testing

To run the tests, use the following command:
```
pytest
```

Make sure you have `pytest` installed in your virtual environment.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your changes. Ensure that your code adheres to the project's coding standards and includes appropriate tests.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.