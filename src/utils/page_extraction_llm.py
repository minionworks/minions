class OpenAIPageExtractionLLM:
    """
    Uses OpenAI's ChatCompletion to extract content from the page based on a given prompt.
    """
    async def invoke(self, prompt: str):
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a page extraction assistant. Extract the relevant information based on the provided goal and page. "
                    "Return your response in JSON format without any additional text."
                )
            },
            {"role": "user", "content": prompt}
        ]
        response = await aclient.chat.completions.create(model="gpt-4o",
        messages=messages,
        temperature=0.0)
        answer = response.choices[0].message['content'].strip()

        class Output:
            def __init__(self, content):
                self.content = content

        return Output(content=answer)