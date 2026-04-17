
import os
import json
import urllib.request
import html
from dotenv import load_dotenv
from google import genai

load_dotenv()

def test_opentdb():
    print("Testing OpenTDB...")
    url = 'https://opentdb.com/api.php?amount=30&type=multiple'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        print(f"OpenTDB Response Code: {data.get('response_code')}")
        if data.get('response_code') == 0:
            print("OpenTDB OK")
            return data.get('results', [])
        else:
            print("OpenTDB Failed")
            return None
    except Exception as e:
        print(f"OpenTDB Error: {e}")
        return None

def test_gemini():
    print("Testing Gemini...")
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("No GEMINI_API_KEY found")
        return False
    
    try:
        client = genai.Client(api_key=api_key)
        # Testing with the model name in the code
        # model_name = 'gemini-3.1-flash-lite-preview' 
        # I'll try a known good one first if that fails
        model_name = 'gemini-2.0-flash' 
        
        prompt = "Hello, respond with 'OK' if you are working."
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        print(f"Gemini Response: {response.text}")
        return True
    except Exception as e:
        print(f"Gemini Error with {model_name}: {e}")
        # Try a fallback if needed
        model_name_in_code = 'gemini-1.5-flash-latest'


        try:
             response = client.models.generate_content(
                model=model_name_in_code,
                contents=prompt,
            )
             print(f"Gemini Response with {model_name_in_code}: {response.text}")
             return True
        except Exception as e2:
             print(f"Gemini Error with {model_name_in_code}: {e2}")
        return False

if __name__ == "__main__":
    test_opentdb()
    test_gemini()
