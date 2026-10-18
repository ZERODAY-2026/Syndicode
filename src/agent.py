import sqlglot
from sqlglot import exp
from src.snowflake_client import get_schema_metadata, execute_sql
from src.gemma_client import generate_plan, explain_results
from src.ingest import ingest_dataset

def verify_plan(plan: dict) -> tuple[bool, str]:
    if plan.get("status") != "success":
        return False, plan.get("reason", "Unsupported query.")
    
    sql = plan.get("sql_query")
    if not sql:
        return False, "Plan did not contain a SQL query."

    try:
        parsed = sqlglot.parse(sql, read="snowflake")[0]
        if not isinstance(parsed, (exp.Select, exp.Union)):
            return False, "Security Block: Only SELECT queries are allowed."
        
        if not parsed.args.get("limit"):
            sql = f"{sql.rstrip(';')} LIMIT 50;"
            
        return True, sql
    except Exception as e:
        return False, f"Invalid SQL syntax: {e}"

def run_agent(question: str, file_path: str = None):
    print(f"\n--- NEW REQUEST ---")
    print(f"User Question: {question}")
    
    if file_path:
        print(f"\n[Ingesting Dataset]: {file_path}")
        success, msg = ingest_dataset(file_path, "CUSTOM_DATA")
        if not success:
            print(f"Ingestion Failed: {msg}")
            return {"answer": f"Failed to load dataset: {msg}", "evidence": None}
        print(f"Ingestion Success: {msg}")
    else:
        print("\n[No dataset provided. Using default Snowflake tables.]")

    schema = get_schema_metadata()
    if not schema:
        return {"answer": "I don't see any data in the database. Please upload a dataset.", "evidence": None}
    
    plan = generate_plan(question, schema)
    print(f"\n[1. Gemma Plan]: {plan}")
    
    is_valid, result = verify_plan(plan)
    if not is_valid:
        print(f"\n[2. Verification Failed]: {result}")
        return {"answer": result, "evidence": None}
    
    safe_sql = result
    print(f"\n[2. Verified SQL]: {safe_sql}")
    
    print("\n[3. Executing in Snowflake...]")
    try:
        evidence = execute_sql(safe_sql)
        evidence["sql_query"] = safe_sql 
        print(f" -> Query ID: {evidence['query_id']}")
        print(f" -> Rows returned: {len(evidence['rows'])}")
    except Exception as e:
        print(f"Snowflake Error: {e}")
        return {"answer": "Database error occurred.", "evidence": None}

    if len(evidence["rows"]) == 0:
        return {"answer": "The database returned no records for this query.", "evidence": evidence}

    print("\n[4. Gemma Explaining...]")
    explanation = explain_results(question, evidence)
    
    return {
        "answer": explanation,
        "evidence": evidence
    }

# --- THIS IS THE PART YOU WERE MISSING ---
if __name__ == "__main__":
    print("=== TEST: REAL SNOWFLAKE DATASET ===")
    
    # Ask a question about the real TPC-H sample data
    question = "What are the names and account balances of the top 3 customers with the highest account balance?"
    
    # Notice we are NOT passing a file_path here, so it uses the default database tables
    result = run_agent(question)
    
    print("\n" + "="*50)
    print("FINAL ANSWER:")
    print(result["answer"])
    print("="*50)