import logging
import re

import pandas as pd
import streamlit as st

from src.agent import run_agent, run_uploaded_agent
from src.charts import chart_dataframe
from src.config import SF_CONFIG


logger = logging.getLogger(__name__)
MAX_UPLOAD_MB = 200
REQUIRED_SNOWFLAKE_SETTINGS = (
    "account",
    "user",
    "password",
    "warehouse",
    "database",
    "schema",
)

st.set_page_config(
    page_title="DataMind",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _snowflake_missing_settings() -> list[str]:
    return [
        key.upper()
        for key in REQUIRED_SNOWFLAKE_SETTINGS
        if not SF_CONFIG.get(key)
    ]


def _uploaded_table_name(filename: str, used_names: set[str]) -> str:
    raw_name = re.sub(r"[^A-Za-z0-9_]+", "_", filename.rsplit(".", 1)[0])
    table_name = raw_name.upper().strip("_") or "UPLOADED_DATA"
    if table_name[0].isdigit():
        table_name = f"DATA_{table_name}"
    base_name = table_name
    suffix = 2
    while table_name in used_names:
        table_name = f"{base_name}_{suffix}"
        suffix += 1
    used_names.add(table_name)
    return table_name


def _read_uploaded_datasets(uploaded_files, upload_limit_mb: int) -> dict:
    datasets = {}
    used_names = set()
    for uploaded_file in uploaded_files or []:
        if uploaded_file.size > upload_limit_mb * 1024 * 1024:
            st.error(
                f"A selected CSV is larger than the {upload_limit_mb} MB "
                "per-file limit."
            )
            continue
        try:
            frame = pd.read_csv(uploaded_file)
            if frame.empty and len(frame.columns) == 0:
                st.warning("A selected CSV has no columns to query.")
                continue
        except pd.errors.EmptyDataError:
            st.warning("An empty CSV was skipped.")
            continue
        except (UnicodeDecodeError, pd.errors.ParserError, ValueError):
            st.error(
                "A selected file could not be read. Check that it is a "
                "well-formed, UTF-8-compatible CSV file."
            )
            continue

        table_name = _uploaded_table_name(uploaded_file.name, used_names)
        datasets[table_name] = frame
    return datasets


def _render_chart(chart: dict, evidence: dict) -> None:
    chart_data = chart_dataframe(chart, evidence)
    st.text(chart["title"])
    if chart["type"] == "bar":
        st.bar_chart(chart_data, x=chart["x"], y=chart["y"])
    elif chart["type"] == "line":
        st.line_chart(chart_data, x=chart["x"], y=chart["y"])
    elif chart["type"] == "scatter":
        st.scatter_chart(chart_data, x=chart["x"], y=chart["y"])


with st.sidebar:
    st.markdown("## Data source")
    source_mode = st.radio(
        "Choose where to query",
        ["Snowflake", "CSV uploads"],
        captions=[
            "Query tables in your configured Snowflake schema.",
            "Analyze files locally in this browser session.",
        ],
        horizontal=False,
        label_visibility="collapsed",
    )

    uploaded_datasets = {}
    selected_dataset = None
    if source_mode == "Snowflake":
        missing_settings = _snowflake_missing_settings()
        if missing_settings:
            st.warning(
                "Snowflake setup is incomplete. Missing: "
                f"{', '.join(missing_settings)}. Add these settings to the root "
                "`.env` file. CSV uploads work without Snowflake."
            )
        else:
            st.success("Snowflake settings found")
        dataset_input = st.text_input(
            "Table (optional)",
            placeholder="Auto-select",
            help="Enter one table name from the configured schema, or leave blank "
            "to let the assistant choose.",
        )
        selected_dataset = dataset_input.strip() or None
    else:
        upload_limit = st.number_input(
            "Maximum size per CSV (MB)",
            min_value=1,
            max_value=MAX_UPLOAD_MB,
            value=50,
            help="Files are parsed in memory; large files use more memory.",
        )
        uploaded_files = st.file_uploader(
            "Choose CSV files",
            type=["csv"],
            accept_multiple_files=True,
            help="Files are analyzed locally and are not uploaded to Snowflake.",
        )
        uploaded_datasets = _read_uploaded_datasets(
            uploaded_files, int(upload_limit)
        )
        if uploaded_datasets:
            selected_option = st.selectbox(
                "Dataset",
                ["Auto-select", *uploaded_datasets.keys()],
            )
            selected_dataset = (
                None if selected_option == "Auto-select" else selected_option
            )
            st.caption(
                f"{len(uploaded_datasets)} dataset(s) ready · "
                f"{sum(len(frame) for frame in uploaded_datasets.values()):,} total rows"
            )
            with st.expander("Preview uploaded data", expanded=False):
                for table_name, frame in uploaded_datasets.items():
                    st.markdown(f"**{table_name}** · {len(frame):,} rows")
                    st.dataframe(frame.head(5), hide_index=True, use_container_width=True)
        else:
            st.info("Add a CSV to start. Each file becomes a queryable dataset.")

    st.divider()
    st.caption(
        "Questions, schema, and returned rows are sent to your configured Ollama "
        "service. See the README for privacy and network details."
    )

st.caption("DATAMIND  /  DATA EXPLORATION")
st.title("Ask your data.")
st.markdown(
    "Explore a Snowflake schema or a CSV with a natural-language question. "
    "Review the verified SQL, results, and any chart suggested by the returned data."
)

with st.form("question_form", clear_on_submit=False, border=True):
    question = st.text_area(
        "What would you like to know?",
        key="question_input",
        placeholder="For example: Which regions had the highest sales last month?",
        height=100,
        max_chars=1000,
    )
    run_disabled = (
        source_mode == "CSV uploads" and not uploaded_datasets
    ) or (
        source_mode == "Snowflake" and bool(_snowflake_missing_settings())
    )
    submitted = st.form_submit_button(
        "Analyze data",
        type="primary",
        use_container_width=True,
        disabled=run_disabled,
    )

if source_mode == "CSV uploads" and not uploaded_datasets:
    st.info("Upload at least one readable CSV file in the sidebar to enable analysis.")
elif source_mode == "Snowflake" and _snowflake_missing_settings():
    st.info("Add the Snowflake settings shown in the setup guide, or switch to CSV uploads.")

if submitted:
    if not question.strip():
        st.warning("Enter a question before submitting.")
    else:
        try:
            with st.spinner("Planning, verifying, and analyzing your data..."):
                if source_mode == "Snowflake":
                    result = run_agent(question.strip(), selected_dataset)
                else:
                    result = run_uploaded_agent(
                        question.strip(), uploaded_datasets, selected_dataset
                    )
            st.session_state["last_run"] = result
            st.session_state["last_run_context"] = {
                "question": question.strip(),
                "source": source_mode,
                "dataset": selected_dataset,
            }
        except Exception:
            logger.exception("Data request failed.")
            st.session_state.pop("last_run", None)
            st.session_state.pop("last_run_context", None)
            if source_mode == "Snowflake" and _snowflake_missing_settings():
                st.error(
                    "Snowflake is not configured. Add the required settings to "
                    "`.env`, then restart the app. See the README troubleshooting guide."
                )
            else:
                st.error(
                    "The request could not be completed. Check that Ollama is "
                    "running with `gemma3n:e4b` available and, for Snowflake, "
                    "that your account, role, warehouse, and schema are accessible."
                )

result = st.session_state.get("last_run")
run_context = st.session_state.get("last_run_context", {})
if result:
    st.divider()
    st.markdown("### Latest analysis")
    context_columns = st.columns([3, 1])
    with context_columns[0]:
        if run_context.get("question"):
            st.caption("Question")
            st.text(run_context["question"])
    with context_columns[1]:
        if run_context.get("source"):
            st.caption(f"Source · {run_context['source']}")

    evidence = result.get("evidence")
    if evidence is None:
        plan = result.get("plan") or {}
        if plan.get("status") in {"unsupported", "error"}:
            st.warning("This question could not be answered.")
        else:
            st.error("The query could not be completed.")
        st.text(result.get("answer", "No additional details were returned."))
        if result.get("sql_query"):
            with st.expander("Generated SQL", expanded=False):
                st.code(result["sql_query"], language="sql")
    else:
        st.success("Query completed")
        st.markdown("#### Answer")
        st.text(result.get("answer", "No summary was returned."))

        chart = result.get("chart")
        if chart:
            _render_chart(chart, evidence)
        elif result.get("chart_reason"):
            st.text(f"No chart shown · {result['chart_reason']}")

        columns = evidence.get("columns", [])
        rows = evidence.get("rows", [])
        st.markdown("#### Results")
        st.caption(
            f"{len(rows):,} row(s) · "
            + (
                "Local CSV analysis"
                if evidence.get("query_id") == "local-upload"
                else f"Snowflake query `{evidence.get('query_id', 'N/A')}`"
            )
        )
        if rows:
            st.dataframe(
                pd.DataFrame(rows, columns=columns),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("The query completed successfully but returned no rows.")

    plan = result.get("plan")
    sql_query = result.get("sql_query")
    if plan or sql_query:
        with st.expander("Query details", expanded=False):
            if sql_query:
                st.markdown("**Executed SQL**" if evidence is not None else "**SQL**")
                st.code(sql_query, language="sql")
            if plan:
                st.markdown("**Plan**")
                st.json(plan)

with st.expander("About data handling", expanded=False):
    st.markdown(
        "- Uploaded CSV files are read into memory and queried using temporary "
        "SQLite storage; they are not written to Snowflake.\n"
        "- The question, schema, and result rows are sent to the configured "
        "Ollama endpoint for planning or summarization.\n"
        "- Snowflake mode sends verified read-only SQL to the configured account.\n"
        "- See `README.md` for setup, permissions, troubleshooting, and privacy details."
    )
