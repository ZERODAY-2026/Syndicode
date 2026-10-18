import logging
import re

import pandas as pd
import streamlit as st

from src.agent import run_agent, run_uploaded_agent


logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="DataMind | Data Assistant",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    :root {
        --bg: #0B1220;
        --surface: #111E2D;
        --border: #283D4D;
        --text: #E5F0F2;
        --muted: #91A8B4;
        --teal: #75BDB4;
    }
    .stApp { background: var(--bg); color: var(--text); }
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .hero { padding: 28px 0 22px; }
    .eyebrow {
        color: var(--teal);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
    }
    .hero-title {
        color: var(--text);
        font-family: 'Manrope', sans-serif;
        font-size: clamp(30px, 5vw, 46px);
        font-weight: 800;
        margin: 8px 0;
    }
    .hero-description { color: var(--muted); font-size: 15px; }
    [data-testid="stForm"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <div class="eyebrow">Intelligent data exploration</div>
        <div class="hero-title">Ask your data anything.</div>
        <div class="hero-description">
            Choose a Snowflake dataset, ask a question, and review the verified query and results.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

source_mode = st.radio(
    "Data source",
    ["Snowflake", "Upload CSV files"],
    horizontal=True,
)

uploaded_datasets = {}
if source_mode == "Upload CSV files":
    upload_limit = st.number_input(
        "Maximum size per CSV (MB)",
        min_value=1,
        max_value=200,
        value=50,
        help="Large files use more app memory. Files are kept only in this browser session.",
    )
    uploaded_files = st.file_uploader(
        "Add CSV files",
        type=["csv"],
        accept_multiple_files=True,
        help="Each CSV becomes a queryable dataset for this app session only.",
    )
    used_names = set()
    for uploaded_file in uploaded_files or []:
        raw_table_name = re.sub(
            r"[^A-Za-z0-9_]+", "_", uploaded_file.name.rsplit(".", 1)[0]
        )
        table_name = raw_table_name.upper().strip("_") or "UPLOADED_DATA"
        if table_name[0].isdigit():
            table_name = f"DATA_{table_name}"
        base_name = table_name
        suffix = 2
        while table_name in used_names:
            table_name = f"{base_name}_{suffix}"
            suffix += 1
        used_names.add(table_name)

        if uploaded_file.size > upload_limit * 1024 * 1024:
            st.error(f"{uploaded_file.name} exceeds the selected upload size limit.")
            continue
        try:
            uploaded_datasets[table_name] = pd.read_csv(uploaded_file)
            st.success(
                f"Added {uploaded_file.name} as {table_name} "
                f"({len(uploaded_datasets[table_name]):,} rows)"
            )
        except (UnicodeDecodeError, pd.errors.ParserError, ValueError):
            st.error(f"{uploaded_file.name} could not be read as a CSV file.")

with st.form("question_form", clear_on_submit=False):
    question = st.text_input(
        "Your question",
        placeholder="e.g. What are the names of the first 3 users?",
    )
    if source_mode == "Snowflake":
        dataset = st.text_input(
            "Dataset (optional)",
            placeholder="e.g. USERS",
            help="Enter a Snowflake table name, or leave blank for automatic selection.",
        )
        selected_dataset = dataset.strip() or None
    else:
        dataset_options = ["Auto-select"] + list(uploaded_datasets)
        selected = st.selectbox("Dataset", dataset_options)
        selected_dataset = None if selected == "Auto-select" else selected
    submitted = st.form_submit_button("Ask your data", type="primary")

if submitted:
    if not question.strip():
        st.session_state.pop("last_run", None)
        st.warning("Enter a question before submitting.")
    else:
        try:
            with st.spinner("Planning, verifying, and querying your data..."):
                if source_mode == "Snowflake":
                    st.session_state["last_run"] = run_agent(
                        question.strip(), selected_dataset
                    )
                else:
                    st.session_state["last_run"] = run_uploaded_agent(
                        question.strip(), uploaded_datasets, selected_dataset
                    )
        except Exception:
            logger.exception("Data request failed.")
            st.session_state.pop("last_run", None)
            st.error(
                "The request could not be completed. Check that Snowflake and Ollama "
                "are configured and available, then try again."
            )

result = st.session_state.get("last_run")
if result:
    st.divider()

    if result.get("evidence") is None:
        if result.get("plan", {}).get("status") != "success":
            st.warning(result.get("answer", "The request could not be answered."))
        else:
            st.error(result.get("answer", "The request could not be completed."))
    else:
        st.subheader("Answer")
        st.markdown(result.get("answer", "No summary was returned."))

    sql_query = result.get("sql_query")
    if sql_query:
        st.subheader("Executed SQL")
        st.code(sql_query, language="sql")

    plan = result.get("plan")
    if plan:
        with st.expander("Plan details", expanded=False):
            st.json(plan)
            plan_file = result.get("plan_file")
            if plan_file:
                st.caption(f"Persisted plan: `{plan_file}`")

    evidence = result.get("evidence")
    if evidence is not None:
        st.subheader("Query results")
        query_id = evidence.get("query_id", "N/A")
        query_label = (
            "Local uploaded-file query"
            if query_id == "local-upload"
            else f"Snowflake query ID: {query_id}"
        )
        st.caption(query_label)
        columns = evidence.get("columns", [])
        rows = evidence.get("rows", [])
        if rows:
            st.dataframe(
                pd.DataFrame(rows, columns=columns),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("The query completed but returned no rows.")
