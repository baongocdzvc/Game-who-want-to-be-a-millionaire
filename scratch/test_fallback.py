
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

def test_fallback():
    api_key = os.getenv('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    model_name = 'models/gemini-1.5-flash-latest'
    print(f"Testing with {model_name}...")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents="Hello, respond with 'OK'."
        )
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_fallback()
