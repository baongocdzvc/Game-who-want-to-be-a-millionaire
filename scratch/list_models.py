
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

def list_models():
    api_key = os.getenv('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    print("Listing models...")
    try:
        for model in client.models.list():
            print(f"Model: {model.name}, Supported: {model.supported_actions}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_models()
