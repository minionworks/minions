import json

class OpenAIGPT:
    """
    Uses OpenAI's ChatCompletion to analyze function outputs and decide the next action.
    """
    def __init__(self, client):
        self.client = client
        

    async def analyze(self, input_text: str) -> dict:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a web scraper controller that decides the next action based on the output of previous function calls. "
                    "Return a JSON object that strictly follows one of these formats:\n"
                    '- For navigation: {"action": "go_to_url", "url": "https://example.com"}\n'
                    '- For waiting: {"action": "wait", "seconds": 3}\n'
                    '- For content extraction: {"action": "extract_content"}\n'
                    '- To finish: {"action": "final", "output": "Final message here. It Should summarize the given content"}\n'
                    "Do not include any extra text."
                )
            },
            {"role": "user", "content": f"Input: {input_text}"}
        ]
        
        response = await self.client.chat.completions.create(model="gpt-4o",
        messages=messages,
        temperature=0.0)
        
        answer = response.choices[0].message.content.strip()

        try:
            result = json.loads(answer)
        except Exception as e:
            result = {"action": "final", "output": f"Failed to parse GPT output: {answer}"}
        
        return result