from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
import os

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL")
)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "Привет! Как дела?"}
    ]
)

print(response.choices[0].message.content)