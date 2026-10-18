import ollama
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("OLLAMA_HOST")
client = ollama.Client(host=url)

print(f"Fetching models from: {url}")
try:
    models = client.list()
    print("\n--- AVAILABLE MODELS ON SAYAN'S LAPTOP ---")
    for m in models['models']:
        print(f"-> {m['name']}")
    print("------------------------------------------")
except Exception as e:
    print(f"Failed: {e}")