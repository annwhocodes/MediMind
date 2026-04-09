from groq import Groq
import logging

logger = logging.getLogger(__name__)

class GroqGenerativeModel:
    def __init__(self, api_key: str, model_name: str = 'llama-3.3-70b-versatile'):
        self.client = Groq(api_key=api_key)
        self.model_name = model_name

    def generate_content(self, prompt: str):
        class Response:
            def __init__(self, text):
                self.text = text
        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            return Response(completion.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error calling Groq API: {e}")
            raise
