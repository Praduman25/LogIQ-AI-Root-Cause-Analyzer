import os
from openai import OpenAI
from dotenv import load_dotenv

from prompts import get_rca_prompt
from utils import clean_logs

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "http://localhost:8501",
        "X-Title": "LogIQ"
    }
)


def analyze_logs(logs):
    try:
        cleaned_logs = clean_logs(logs)
        prompt = get_rca_prompt(cleaned_logs)

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"❌ Error: {str(e)}"