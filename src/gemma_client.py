import ollama
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Connect to Sayan's laptop using the IP from the .env file
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
client = ollama.Client(host=OLLAMA_URL)
MODEL = "gemma3n:e4b"

def generate_plan(question: str, schema_metadata: list) -> dict:
    """Step 1: Gemma generates plan.json"""
    
    schema_str = "\n".join([f"- {t}.{c} ({d})" for t, c, d in schema_metadata])
    
    prompt = f"""You are an AI Data Planner. 
The user asked: "{question}"
Available Schema:
{schema_str}

Create a JSON plan with these exact keys:
- "status": "success" or "unsupported"
- "reason": If unsupported, why. Else null.
- "sql_query": The Snowflake SELECT query to answer the question.

Output ONLY valid JSON. Do not include markdown formatting like ```json."""

    # Use client.chat instead of ollama.chat to connect to Sayan's laptop
    response = client.chat(model=MODEL, messages=[{'role': 'user', 'content': prompt}])
    raw_text = response['message']['content'].strip()
    
    # Clean up just in case
    raw_text = raw_text.replace('```json', '').replace('```', '').strip()
    
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {"status": "error", "reason": "Gemma failed to generate valid JSON."}

def explain_results(question: str, evidence: dict) -> str:
    """Step 4: Gemma explains the verified answer"""
    prompt = f"""You are a helpful Data Analyst.
User Question: "{question}"
Executed SQL: {evidence.get('query_id', 'N/A')}
Data Columns: {evidence['columns']}
Data Rows: {evidence['rows'][:10]} (showing max 10)

Write a short, plain-English summary answering the user's question using ONLY the data provided."""

    # Use client.chat here too!
    response = client.chat(model=MODEL, messages=[{'role': 'user', 'content': prompt}])
    return response['message']['content'].strip()