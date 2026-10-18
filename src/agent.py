import sqlglot
from sqlglot import exp
from src.snowflake_client import get_schema_metadata, execute_sql
from src.gemma_client import generate_plan, explain_results

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
            sql = f"{sql.rstrip(';')} LIMIT 100;"
            
        return True, sql
    except Exception as e:
        return False, f"Invalid SQL syntax: {e}"

def run_agent(question: str):
    print(f"\n[User]: {question}")
    
    schema = get_schema_metadata()
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

if __name__ == "__main__":
    # You can change this question later!
    test_question = "What are the names of the first 3 users?"
    result = run_agent(test_question)
    
    print("\n" + "="*50)
    print("FINAL OUTPUT TO USER:")
    print(result["answer"])
    print("="*50)




    