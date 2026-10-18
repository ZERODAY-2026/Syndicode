import ollama
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("OLLAMA_HOST")
print(f"Trying to connect to Ollama at: {url}")

client = ollama.Client(host=url)

try:
    response = client.chat(model='gemma3n:e4b', messages=[{'role': 'user', 'content': 'Say "Hello from Sayan\'s laptop!"'}])
    print(response['message']['content'])
except Exception as e:
    print(f"CONNECTION FAILED: {e}")