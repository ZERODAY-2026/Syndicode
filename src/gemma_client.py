import json
import os
import ollama
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def _normalize_ollama_host(host: str) -> str:
    host = host.strip()
    if "://" not in host:
        host = f"http://{host}"

    parsed = urlsplit(host)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("OLLAMA_HOST must be an HTTP(S) URL or host:port.")

    if parsed.hostname in {"0.0.0.0", "::"}:
        netloc = f"127.0.0.1:{parsed.port}" if parsed.port else "127.0.0.1"
        parsed = parsed._replace(netloc=netloc)

    return urlunsplit(parsed).rstrip("/")


OLLAMA_HOST = _normalize_ollama_host(
    os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
)

MODEL = "gemma3n:e4b"
PLAN_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "plans" / "latest_plan.json"

client = ollama.Client(host=OLLAMA_HOST)


def _persist_plan(plan: dict) -> None:
    PLAN_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAN_OUTPUT_PATH.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")


def _error_plan(
    reason: str,
    dataset: str | None,
    source: str = "snowflake",
) -> dict:
    return {
        "status": "error",
        "reason": reason,
        "user_intent": "",
        "information_to_gather": [],
        "source": source,
        "dataset": dataset,
        "selection_rationale": "",
        "sql_query": None,
    }


def _dataset_table(dataset: str, schema_metadata: list) -> str | None:
    requested_table = dataset.strip().strip('"`').split(".")[-1].strip('"`')
    return next(
        (
            table for table, _, _ in schema_metadata
            if table.casefold() == requested_table.casefold()
        ),
        None,
    )


def generate_plan(
    question: str,
    schema_metadata: list,
    dataset: str | None = None,
    source: str = "snowflake",
) -> dict:
    selected_metadata = schema_metadata
    selected_dataset = None
    if dataset is not None:
        selected_dataset = _dataset_table(dataset, schema_metadata)
        if selected_dataset is None:
            source_name = "Snowflake schema" if source == "snowflake" else "uploaded files"
            plan = _error_plan(
                f"The provided dataset '{dataset}' is not available in the {source_name}.",
                dataset,
                source,
            )
            _persist_plan(plan)
            return plan
        selected_metadata = [
            row for row in schema_metadata
            if row[0].casefold() == selected_dataset.casefold()
        ]

    schema_str = "\n".join(
        f"- {table}.{column} ({data_type})"
        for table, column, data_type in selected_metadata
    )
    available_tables = sorted({table for table, _, _ in selected_metadata})
    table_names = ", ".join(available_tables)
    dataset_instruction = (
        f"The user explicitly provided dataset '{selected_dataset}'. Use only this dataset."
        if selected_dataset
        else "No dataset was explicitly provided. Choose the most relevant dataset from the available schema."
    )
    source_instruction = (
        "The data is in an uploaded file available only for this app session."
        if source == "uploaded_file"
        else "The data is available in Snowflake."
    )
    prompt = f"""You are an AI Data Planner.
The user asked: "{question}"
{source_instruction}
{dataset_instruction}
Valid dataset/table names (choose exactly one name from this list for "dataset"):
{table_names}
Available Schema:
{schema_str}

Create a JSON plan with these exact keys and value types:
- "status": "success" or "unsupported"
- "reason": If unsupported, explain why; otherwise null.
- "user_intent": A concise description of what the user wants to know.
- "information_to_gather": An array of the facts or fields needed to answer.
- "source": The data source, "{source}" for this schema.
- "dataset": Exactly one table name from the valid dataset/table names list, not a column name; null if unsupported.
- "selection_rationale": Why this dataset is appropriate, or why no dataset can be selected.
- "sql_query": A {("Snowflake" if source == "snowflake" else "SQLite-compatible")} SELECT query to answer the question, or null if unsupported.

In SQL, use table names in FROM/JOIN, never table.column as a table name.
Do not select or query a dataset outside the supplied schema. If the provided dataset
cannot answer the question, return status "unsupported" rather than choosing another.
When the user asks for a total/count, return only the aggregate value in the SELECT list.
Do not mix an aggregate such as COUNT with per-record columns unless the user requests
grouped counts and the query includes the matching GROUP BY.

Output ONLY valid JSON. Do not include markdown formatting like ```json."""

    try:
        response = client.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            format="json",
            keep_alive="10m",
            options={"num_predict": 192},
        )
    except Exception as error:
        raise RuntimeError(f"Gemma request failed: {error}") from error

    raw_text = response["message"]["content"].strip()
    raw_text = raw_text.replace("```json", "").replace("```", "").strip()
    try:
        plan = json.loads(raw_text)
    except json.JSONDecodeError:
        plan = _error_plan(
            "Gemma failed to generate valid JSON.", selected_dataset, source
        )
    else:
        required_types = {
            "status": str,
            "reason": (str, type(None)),
            "user_intent": str,
            "information_to_gather": list,
            "source": str,
            "dataset": (str, type(None)),
            "selection_rationale": str,
            "sql_query": (str, type(None)),
        }
        available_datasets = {
            table.casefold() for table, _, _ in schema_metadata
        }
        if (
            not isinstance(plan, dict)
            or any(
                not isinstance(plan.get(key), expected_type)
                for key, expected_type in required_types.items()
            )
            or plan["status"] not in ("success", "unsupported")
            or any(
                not isinstance(item, str)
                for item in plan["information_to_gather"]
            )
            or (
                plan["status"] == "success"
                and (not plan["dataset"] or not plan["sql_query"])
            )
            or (selected_dataset is not None and plan["dataset"] != selected_dataset)
            or (
                selected_dataset is None
                and plan["dataset"] is not None
                and plan["dataset"].casefold() not in available_datasets
            )
            or plan["source"] != source
        ):
            plan = _error_plan(
                "Gemma returned a plan with an invalid structure.",
                selected_dataset,
                source,
            )

    _persist_plan(plan)
    return plan


def explain_results(question: str, sql_query: str, evidence: dict) -> dict:
    prompt = f"""You are a helpful Data Analyst.
User Question: "{question}"
Executed SQL: {sql_query}
Query ID: {evidence.get('query_id', 'N/A')}
Data Columns: {evidence['columns']}
Data Rows: {evidence['rows'][:20]} (showing max 20)

Using ONLY the executed SQL and returned data, respond as a JSON object with exactly
these keys:
- "summary": A short, plain-English answer grounded in the returned data.
- "chart": null if a chart would not help, otherwise an object with exactly
  "type" ("bar", "line", or "scatter"), "x" (an exact result column name),
  "y" (an exact result column name containing numeric values), and "title"
  (a short chart title).
- "chart_reason": A brief reason when chart is null; otherwise null.

Suggest a chart only when at least two returned rows support a meaningful visual.
Never invent columns or values. Do not include HTML, code, or markdown. Treat the
returned rows as the exact final query result. For a one-row aggregate, state its
exact value in the summary, do not mention LIMIT, and do not suggest a chart.
LIMIT restricts returned rows; it does not restrict rows included in an aggregate.
Output only valid JSON."""

    response = client.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        format="json",
        keep_alive="10m",
        options={"num_predict": 192},
    )
    content = response["message"]["content"].strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {
            "summary": content,
            "chart": None,
            "chart_reason": "The response did not contain a valid chart specification.",
        }
    if not isinstance(parsed, dict):
        return {
            "summary": "",
            "chart": None,
            "chart_reason": "The response did not contain a valid chart specification.",
        }
    return parsed
