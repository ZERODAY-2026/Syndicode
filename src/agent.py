import re
import sqlite3

import sqlglot
from sqlglot import exp
from src.snowflake_client import get_schema_metadata, execute_sql
from src.gemma_client import PLAN_OUTPUT_PATH, generate_plan, explain_results


def _normalized_name(name: str) -> str:
    return name.strip('"`').casefold()


def verify_dataset_compatibility(
    plan: dict,
    schema_metadata: list,
    explicit_dataset: str | None = None,
) -> tuple[bool, str]:
    if plan.get("status") != "success":
        return False, plan.get("reason") or "The plan is not marked as supported."

    available_columns: dict[str, set[str]] = {}
    for table, column, _ in schema_metadata:
        available_columns.setdefault(_normalized_name(table), set()).add(
            _normalized_name(column)
        )

    selected_dataset = plan.get("dataset")
    if not isinstance(selected_dataset, str) or not selected_dataset.strip():
        return False, "Plan did not select an available dataset."

    selected_name = _normalized_name(selected_dataset.split(".")[-1])
    if selected_name not in available_columns:
        return False, f"Selected dataset '{selected_dataset}' is not available."

    if explicit_dataset is not None:
        requested_name = _normalized_name(explicit_dataset.split(".")[-1])
        if selected_name != requested_name:
            return False, (
                f"The plan selected '{selected_dataset}' instead of "
                f"'{explicit_dataset}'."
            )

    sql = plan.get("sql_query")
    if not isinstance(sql, str) or not sql.strip():
        return False, "Plan did not contain a SQL query."

    try:
        parsed = sqlglot.parse(sql, read="snowflake")
    except Exception as error:
        return False, f"Invalid SQL syntax: {error}"
    if len(parsed) != 1 or not isinstance(parsed[0], (exp.Select, exp.Union)):
        return False, "Security Block: Only a single SELECT query is allowed."

    table_aliases: dict[str, str] = {}
    query_tables: set[str] = set()
    for table in parsed[0].find_all(exp.Table):
        if table.db or table.catalog:
            return False, "Query must use unqualified tables from the available schema."
        table_name = _normalized_name(table.name)
        if table_name not in available_columns:
            return False, f"Query references unavailable dataset '{table.name}'."
        query_tables.add(table_name)
        table_aliases[_normalized_name(table.alias or table.name)] = table_name

    if not query_tables:
        return False, "Query does not reference an available dataset."
    if selected_name not in query_tables:
        return False, f"Query does not use its selected dataset '{selected_dataset}'."
    if explicit_dataset is not None and query_tables != {selected_name}:
        return False, (
            f"Query must use only the explicitly provided dataset "
            f"'{explicit_dataset}'."
        )

    projection_aliases = {
        _normalized_name(alias.alias)
        for alias in parsed[0].find_all(exp.Alias)
        if alias.alias
    }
    for column in parsed[0].find_all(exp.Column):
        column_name = _normalized_name(column.name)
        if column_name == "*" or column_name in projection_aliases:
            continue
        if column.table:
            source_table = table_aliases.get(_normalized_name(column.table))
            if source_table is None:
                return False, f"Query references unknown table or alias '{column.table}'."
            if column_name not in available_columns[source_table]:
                return False, (
                    f"Column '{column.name}' is not available in dataset "
                    f"'{source_table}'."
                )
        elif not any(
            column_name in available_columns[table_name] for table_name in query_tables
        ):
            return False, (
                f"Column '{column.name}' is not available in the selected dataset(s)."
            )

    return True, ""

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


def _snowflake_error_message(error: Exception) -> str:
    if getattr(error, "errno", None) == 979:
        return (
            "Snowflake rejected the generated SQL because it mixes an aggregate "
            "with a non-aggregated column. For a total count, the query should "
            "return only the count; for grouped counts, include a GROUP BY."
        )
    error_code = getattr(error, "errno", None)
    if error_code is not None:
        return f"Snowflake could not execute the generated SQL (error {error_code})."
    return "Snowflake could not execute the generated SQL."


def _ground_aggregate_summary(sql: str, evidence: dict, summary: str) -> str:
    rows = evidence.get("rows", [])
    columns = evidence.get("columns", [])
    if len(rows) != 1 or len(columns) != 1:
        return summary

    try:
        query = sqlglot.parse_one(sql, read="snowflake")
    except Exception:
        return summary
    if not any(isinstance(node, exp.AggFunc) for node in query.walk()):
        return summary

    value = rows[0][0]
    if isinstance(value, int) and not isinstance(value, bool):
        rendered_value = f"{value:,}"
    else:
        rendered_value = str(value)
    if any(isinstance(node, exp.Count) for node in query.walk()):
        return f"The count is {rendered_value}."
    return f"The query result is {rendered_value}."


def run_agent(question: str, dataset: str | None = None):
    print(f"\n[User]: {question}")
    
    schema = get_schema_metadata()
    plan = generate_plan(question, schema, dataset)
    print(f"\n[1. Gemma Plan]: {plan}")

    can_solve, compatibility_error = verify_dataset_compatibility(
        plan, schema, dataset
    )
    if not can_solve:
        print(f"\n[2. Dataset Verification Failed]: {compatibility_error}")
        return {
            "answer": compatibility_error,
            "evidence": None,
            "plan": plan,
            "plan_file": str(PLAN_OUTPUT_PATH),
            "sql_query": None,
        }
    
    is_valid, result = verify_plan(plan)
    if not is_valid:
        print(f"\n[2. Verification Failed]: {result}")
        return {
            "answer": result,
            "evidence": None,
            "plan": plan,
            "plan_file": str(PLAN_OUTPUT_PATH),
            "sql_query": None,
        }
    
    safe_sql = result
    print(f"\n[2. Verified SQL]: {safe_sql}")
    
    print("\n[3. Executing in Snowflake...]")
    try:
        evidence = execute_sql(safe_sql)
        print(f" -> Query ID: {evidence['query_id']}")
        print(f" -> Rows returned: {len(evidence['rows'])}")
    except Exception as e:
        answer = _snowflake_error_message(e)
        print(f"Snowflake Error: {answer}")
        return {
            "answer": answer,
            "evidence": None,
            "plan": plan,
            "plan_file": str(PLAN_OUTPUT_PATH),
            "sql_query": safe_sql,
        }

    if len(evidence["rows"]) == 0:
        return {
            "answer": "The database returned no records for this query.",
            "evidence": evidence,
            "plan": plan,
            "plan_file": str(PLAN_OUTPUT_PATH),
            "sql_query": safe_sql,
        }

    print("\n[4. Gemma Explaining...]")
    explanation = explain_results(question, safe_sql, evidence)
    explanation = _ground_aggregate_summary(safe_sql, evidence, explanation)
    
    return {
        "answer": explanation,
        "evidence": evidence,
        "plan": plan,
        "plan_file": str(PLAN_OUTPUT_PATH),
        "sql_query": safe_sql,
    }


def run_uploaded_agent(
    question: str,
    datasets: dict,
    dataset: str | None = None,
):
    """Query uploaded pandas DataFrames in an in-memory SQLite database."""
    if not datasets:
        return {
            "answer": "Upload at least one CSV file before asking a question.",
            "evidence": None,
            "plan": None,
            "plan_file": None,
            "sql_query": None,
        }

    for table_name in datasets:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
            raise ValueError("Uploaded dataset names must be valid SQL identifiers.")

    schema = [
        (table_name, str(column), str(data_type))
        for table_name, frame in datasets.items()
        for column, data_type in frame.dtypes.items()
    ]
    plan = generate_plan(question, schema, dataset, source="uploaded_file")
    can_solve, compatibility_error = verify_dataset_compatibility(
        plan, schema, dataset
    )
    if not can_solve:
        return {
            "answer": compatibility_error,
            "evidence": None,
            "plan": plan,
            "plan_file": str(PLAN_OUTPUT_PATH),
            "sql_query": None,
        }

    is_valid, result = verify_plan(plan)
    if not is_valid:
        return {
            "answer": result,
            "evidence": None,
            "plan": plan,
            "plan_file": str(PLAN_OUTPUT_PATH),
            "sql_query": None,
        }

    safe_sql = result
    try:
        with sqlite3.connect(":memory:") as connection:
            for table_name, frame in datasets.items():
                frame.to_sql(table_name, connection, index=False, if_exists="fail")
            sqlite_query = sqlglot.transpile(
                safe_sql, read="snowflake", write="sqlite"
            )[0]
            cursor = connection.execute(sqlite_query)
            evidence = {
                "query_id": "local-upload",
                "columns": [description[0] for description in cursor.description or []],
                "rows": cursor.fetchall(),
            }
    except Exception:
        return {
            "answer": "The uploaded-file query could not be executed.",
            "evidence": None,
            "plan": plan,
            "plan_file": str(PLAN_OUTPUT_PATH),
            "sql_query": safe_sql,
        }

    explanation = (
        explain_results(question, safe_sql, evidence)
        if evidence["rows"]
        else "The uploaded file query completed but returned no rows."
    )
    explanation = _ground_aggregate_summary(safe_sql, evidence, explanation)
    return {
        "answer": explanation,
        "evidence": evidence,
        "plan": plan,
        "plan_file": str(PLAN_OUTPUT_PATH),
        "sql_query": safe_sql,
    }


if __name__ == "__main__":
    # You can change this question later!
    test_question = "What are the names of the first 3 users?"
    result = run_agent(test_question)
    
    print("\n" + "="*50)
    print("FINAL OUTPUT TO USER:")
    print(result["answer"])
    print("="*50)
