import os
import re
import html
import pandas as pd
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import snowflake.connector
    from snowflake.connector.pandas_tools import write_pandas
    SNOWFLAKE_AVAILABLE = True
except ImportError:
    SNOWFLAKE_AVAILABLE = False


st.set_page_config(
    page_title="DataMind | Data Explorer",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');

:root {
    --bg: #0B1220;
    --surface: #111E2D;
    --border: #283D4D;
    --text: #E5F0F2;
    --muted: #91A8B4;
    --teal: #75BDB4;
}

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at 15% 0%, rgba(58,117,119,.17), transparent 34%),
        radial-gradient(circle at 90% 20%, rgba(50,76,111,.12), transparent 30%),
        linear-gradient(135deg, #0B1220, #101B29);
    color: var(--text);
}

.block-container {
    max-width: 1180px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

h1, h2, h3 {
    font-family: 'Manrope', sans-serif !important;
    color: var(--text) !important;
    letter-spacing: -.5px;
}

p, label, .stMarkdown {
    color: var(--text);
}

[data-testid="stHeader"] {
    background: transparent;
}

.brand-row {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 8px;
}

.brand-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 48px;
    height: 48px;
    border-radius: 15px;
    background: linear-gradient(145deg, #1C494D, #17313E);
    border: 1px solid #35666A;
    color: #A8E2D9;
    font-size: 27px;
    font-weight: 800;
}

.brand-name {
    font-family: 'Manrope', sans-serif;
    font-size: 29px;
    font-weight: 800;
    color: #E5F0F2;
    line-height: 1.15;
}

.brand-subtitle {
    color: #91A8B4;
    font-size: 13px;
    margin-top: 4px;
}

.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 6px 11px;
    border: 1px solid #2C4E4E;
    border-radius: 30px;
    background: rgba(40,107,104,.16);
    color: #A6DCD2;
    font-size: 12px;
    white-space: nowrap;
}

.status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #75BDB4;
}

.hero {
    margin-top: 36px;
    margin-bottom: 20px;
}

.eyebrow {
    color: #8FC7C0;
    text-transform: uppercase;
    letter-spacing: 2px;
    font-size: 11px;
    font-weight: 700;
    margin-bottom: 10px;
}

.hero-title {
    font-family: 'Manrope', sans-serif;
    font-size: clamp(28px, 4vw, 43px);
    font-weight: 800;
    line-height: 1.15;
    letter-spacing: -1.5px;
    color: #E5F0F2;
    margin-bottom: 10px;
}

.hero-description {
    color: #91A8B4;
    font-size: 15px;
    line-height: 1.7;
    max-width: 680px;
}

.section-label {
    color: #DCE9EC;
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 8px;
}

.dm-card {
    background: linear-gradient(145deg, rgba(20,34,49,.97), rgba(15,27,40,.97));
    border: 1px solid #283D4D;
    border-radius: 16px;
    padding: 18px;
    transition: border-color .2s ease;
}

.dm-card:hover {
    border-color: #456B70;
}

.stTextInput input, .stNumberInput input {
    background: #111E2D !important;
    color: #E5F0F2 !important;
    border: 1px solid #36545E !important;
    border-radius: 12px !important;
    min-height: 44px;
}

.stTextInput input:focus {
    border-color: #75BDB4 !important;
    box-shadow: 0 0 0 1px #75BDB4 !important;
}

.stTextInput label, .stFileUploader label, .stCheckbox label {
    color: #DCE9EC !important;
}

.stButton > button, .stDownloadButton > button {
    border-radius: 10px;
    min-height: 40px;
    border: 1px solid #36505E;
    background: #152536;
    color: #DCE9EC;
    font-weight: 600;
    transition: all .2s ease;
}

.stButton > button:hover, .stDownloadButton > button:hover {
    border-color: #75BDB4;
    color: #BDE7E1;
    background: #1A303D;
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #347D78, #286B68);
    color: white;
    border: none;
}

.stButton > button[kind="primary"]:hover {
    background: #3C8982;
    color: white;
    border: none;
}

[data-testid="stFileUploader"] {
    background: #0F1C29;
    border: 1px dashed #42656B;
    border-radius: 11px;
    padding: 5px 10px;
}

[data-testid="stFileUploader"]:hover {
    border-color: #83BDB5;
}

[data-testid="stFileUploaderDropzone"] {
    min-height: 65px !important;
    background: #101D2A !important;
    border: none !important;
    padding: 8px 12px !important;
}

[data-testid="stFileUploaderDropzoneInstructions"] {
    color: #B4C7CE !important;
}

[data-testid="stFileUploaderDropzone"] button {
    background: #1B3A40 !important;
    border: 1px solid #42656B !important;
    color: #D5E8E7 !important;
    border-radius: 8px !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    border-bottom: 1px solid #283D4D;
}

.stTabs [data-baseweb="tab"] {
    color: #91A8B4;
    border-radius: 8px 8px 0 0;
}

.stTabs [aria-selected="true"] {
    color: #A8E2D9 !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #283D4D;
    border-radius: 12px;
    overflow: hidden;
}

[data-testid="stExpander"] {
    border: 1px solid #283D4D;
    border-radius: 12px;
    background: rgba(17,30,45,.75);
}

[data-testid="stAlert"] {
    border-radius: 12px;
}

[data-testid="stMetric"] {
    background: rgba(17,30,45,.82);
    border: 1px solid #283D4D;
    border-radius: 13px;
    padding: 14px 16px;
}

[data-testid="stMetricLabel"] {
    color: #91A8B4 !important;
}

[data-testid="stMetricValue"] {
    color: #E5F0F2 !important;
}

.footer {
    text-align: center;
    padding-top: 30px;
    color: #718A98;
    font-size: 12px;
}

@media (max-width: 700px) {
    .block-container {
        padding: 1rem 1rem 2rem;
    }
    .brand-name {
        font-size: 24px;
    }
    .hero {
        margin-top: 24px;
    }
}
</style>
""", unsafe_allow_html=True)


def clean_column_names(df):
    df = df.copy()
    cleaned = []

    for index, col in enumerate(df.columns):
        name = re.sub(r"\s+", "_", str(col).strip())
        name = re.sub(r"[^\w]", "_", name)
        name = re.sub(r"_+", "_", name).strip("_") or f"column_{index + 1}"

        if name[0].isdigit():
            name = f"col_{name}"

        base = name
        suffix = 1
        while name.lower() in {c.lower() for c in cleaned}:
            name = f"{base}_{suffix}"
            suffix += 1

        cleaned.append(name)

    df.columns = cleaned
    return df


def format_value(value):
    if pd.isna(value):
        return "N/A"
    if isinstance(value, float):
        return f"{value:,.4f}".rstrip("0").rstrip(".")
    return str(value)


def answer_question(df, question):
    q = question.lower().strip()
    rows, cols = df.shape

    if not q:
        return "Enter a question to explore your dataset."

    if any(x in q for x in [
        "how many rows", "number of rows", "row count",
        "total rows", "number of records", "how many records",
        "dataset size", "how many entries"
    ]):
        return f"Your dataset contains **{rows:,} rows**."

    if any(x in q for x in [
        "how many columns", "number of columns",
        "column count", "total columns"
    ]):
        return f"Your dataset contains **{cols:,} columns**."

    if any(x in q for x in [
        "column names", "list columns", "what are the columns",
        "show columns", "all columns", "features"
    ]):
        return "Columns in your dataset:\n\n" + "\n".join(
            f"- `{col}`" for col in df.columns
        )

    if any(x in q for x in [
        "missing values", "null values", "missing data",
        "nulls", "empty values"
    ]):
        missing = df.isna().sum()
        missing = missing[missing > 0].sort_values(ascending=False)

        if missing.empty:
            return "There are **no missing values** in this dataset."

        result = missing.rename("Missing values").to_frame()
        result["Percentage"] = (
            result["Missing values"] / max(len(df), 1) * 100
        ).round(2)

        st.dataframe(result, use_container_width=True)
        return f"Found **{int(df.isna().sum().sum()):,} missing cells** across {len(missing)} columns."

    if any(x in q for x in [
        "duplicate rows", "duplicates", "duplicate records"
    ]):
        return f"Your dataset contains **{int(df.duplicated().sum()):,} duplicate rows**."

    if any(x in q for x in [
        "summary", "describe", "statistics",
        "statistical summary", "overview", "eda"
    ]):
        st.dataframe(df.describe(include="all").transpose(), use_container_width=True)
        return "Here is a statistical summary of your dataset."

    if any(x in q for x in [
        "preview", "sample rows", "show data",
        "first rows", "show records", "head"
    ]):
        st.dataframe(df.head(10), use_container_width=True)
        return "Here are the first 10 rows of your dataset."

    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    aggregates = {
        "mean": ["average", "mean"],
        "sum": ["sum", "total of"],
        "min": ["minimum", "smallest", "lowest"],
        "max": ["maximum", "largest", "highest"],
        "median": ["median"],
        "std": ["standard deviation", "std deviation", "stddev"],
    }

    requested = next(
        (agg for agg, phrases in aggregates.items()
         if any(phrase in q for phrase in phrases)),
        None,
    )

    if requested:
        candidates = [
            col for col in numeric_cols
            if str(col).lower() in q
            or str(col).lower().replace("_", " ") in q
        ]

        if len(candidates) == 1:
            col = candidates[0]
            series = df[col].dropna()

            if series.empty:
                return f"Column `{col}` has no numeric values to calculate."

            functions = {
                "mean": series.mean,
                "sum": series.sum,
                "min": series.min,
                "max": series.max,
                "median": series.median,
                "std": series.std,
            }

            return (
                f"The **{requested}** of `{col}` is "
                f"**{format_value(functions[requested]())}**."
            )

        if not candidates:
            return "Specify one numeric column. Available columns: " + ", ".join(
                f"`{c}`" for c in numeric_cols
            )

        return "Please specify one numeric column."

    if any(x in q for x in [
        "unique values", "distinct values", "unique count",
        "number of unique", "distinct count"
    ]):
        candidates = [
            col for col in df.columns
            if str(col).lower() in q
            or str(col).lower().replace("_", " ") in q
        ]

        if len(candidates) == 1:
            col = candidates[0]
            return f"Column `{col}` has **{df[col].nunique(dropna=True):,} unique non-null values**."

        st.dataframe(
            df.nunique(dropna=True).rename("Unique values").to_frame(),
            use_container_width=True,
        )
        return "Here are the unique-value counts for each column."

    if any(x in q for x in [
        "most common", "most frequent", "mode",
        "top category", "most popular"
    ]):
        candidates = [
            col for col in df.columns
            if str(col).lower() in q
            or str(col).lower().replace("_", " ") in q
        ]

        if len(candidates) == 1:
            col = candidates[0]
            modes = df[col].mode(dropna=True)
            if modes.empty:
                return f"Column `{col}` has no non-null values."
            return f"The most common value in `{col}` is **{format_value(modes.iloc[0])}**."

        return "Specify a column to find its most common value."

    if any(x in q for x in [
        "data types", "column types", "schema", "dtypes"
    ]):
        schema = pd.DataFrame({
            "Column": df.columns,
            "Data type": [str(dtype) for dtype in df.dtypes],
            "Non-null values": df.notna().sum().values,
            "Missing values": df.isna().sum().values,
        })
        st.dataframe(schema, use_container_width=True)
        return "Here is the dataset schema."

    if any(x in q for x in ["correlation", "correlated", "correlations"]):
        if len(numeric_cols) < 2:
            return "At least two numeric columns are required for correlation."
        st.dataframe(df[numeric_cols].corr().round(3), use_container_width=True)
        return "Here is the correlation matrix for numeric columns."

    return (
        "I couldn't match that question to a supported operation. "
        "Try asking about rows, columns, missing values, duplicates, "
        "summary statistics, correlations, or the average of a numeric column."
    )


def connect_snowflake():
    if not SNOWFLAKE_AVAILABLE:
        return None, "Snowflake connector is not installed."

    required = [
        "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD", "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE", "SNOWFLAKE_SCHEMA",
    ]

    missing = [key for key in required if not os.getenv(key)]
    if missing:
        return None, "Missing environment variables: " + ", ".join(missing)

    try:
        conn = snowflake.connector.connect(
            user=os.getenv("SNOWFLAKE_USER"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
            database=os.getenv("SNOWFLAKE_DATABASE"),
            schema=os.getenv("SNOWFLAKE_SCHEMA"),
            role=os.getenv("SNOWFLAKE_ROLE") or None,
        )
        return conn, None
    except Exception as exc:
        return None, f"Connection failed: {exc}"


# HEADER
header_left, header_right = st.columns([5, 1])

with header_left:
    st.markdown("""
    <div class="brand-row">
        <div class="brand-icon">◈</div>
        <div>
            <div class="brand-name">DataMind</div>
            <div class="brand-subtitle">Your data, understood.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with header_right:
    st.markdown("""
    <div style="text-align:right; padding-top:8px;">
        <span class="status-pill">
            <span class="status-dot"></span> Workspace
        </span>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# HERO
st.markdown("""
<div class="hero">
    <div class="eyebrow">INTELLIGENT DATA EXPLORATION</div>
    <div class="hero-title">Ask your data anything.</div>
    <div class="hero-description">
        Explore datasets, uncover patterns, and get useful answers
        without writing SQL.
    </div>
</div>
""", unsafe_allow_html=True)

# SEARCH BAR
with st.form("question_form", clear_on_submit=False):
    question_col, submit_col = st.columns([6, 1.15])

    with question_col:
        question = st.text_input(
            "Ask a question",
            placeholder="e.g. What is the average sales amount?",
            label_visibility="collapsed",
        )

    with submit_col:
        submitted = st.form_submit_button(
            "Ask  ↗",
            type="primary",
            use_container_width=True,
        )

# COMPACT UPLOADER DIRECTLY BELOW SEARCH
upload_col, upload_hint_col = st.columns([3, 2])

with upload_col:
    st.markdown(
        '<div class="section-label">＋ Add your dataset</div>',
        unsafe_allow_html=True,
    )
    uploaded_file = st.file_uploader(
        "Choose a CSV or Excel file",
        type=["csv", "xlsx"],
        key="dataset_uploader",
        label_visibility="collapsed",
    )

with upload_hint_col:
    st.markdown("""
    <div style="text-align:right;padding-top:10px;color:#91A8B4;font-size:12px;line-height:1.7;">
        CSV or XLSX<br>Maximum file size depends on Streamlit configuration
    </div>
    """, unsafe_allow_html=True)

# LOAD DATASET
df = None

if uploaded_file is not None:
    try:
        if uploaded_file.name.lower().endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        df = clean_column_names(df)

        if df.empty:
            st.warning("The uploaded file contains no data rows.")
            df = None

    except Exception as exc:
        st.error(f"Could not read the uploaded file: {exc}")

# EXAMPLE QUESTIONS
st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
st.markdown('<div class="section-label">Try asking</div>', unsafe_allow_html=True)

examples = [
    "How many rows are there?",
    "Show missing values",
    "Give me a statistical summary",
    "Show the column names",
]

example_cols = st.columns(4)

for index, example in enumerate(examples):
    with example_cols[index]:
        if st.button(example, key=f"example_{index}", use_container_width=True):
            st.session_state["selected_question"] = example
            st.rerun()

if "selected_question" in st.session_state:
    question = st.session_state.pop("selected_question")
    submitted = True

# DATASET OVERVIEW
if df is None:
    st.markdown("""
    <div class="dm-card" style="margin-top:24px;">
        <div style="font-size:24px;color:#8FC7C0;margin-bottom:8px;">◈</div>
        <div style="font-family:'Manrope',sans-serif;font-size:19px;font-weight:700;color:#E5F0F2;margin-bottom:6px;">
            Your workspace is ready
        </div>
        <div style="font-size:13px;line-height:1.8;color:#91A8B4;">
            Upload a dataset above to begin exploring. Ask questions
            about your data and view the results here.
        </div>
    </div>
    """, unsafe_allow_html=True)

else:
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("### Dataset overview")

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric("Rows", f"{len(df):,}")
    metric2.metric("Columns", f"{len(df.columns):,}")
    metric3.metric("Missing cells", f"{int(df.isna().sum().sum()):,}")
    metric4.metric("Duplicate rows", f"{int(df.duplicated().sum()):,}")

    with st.expander("Preview dataset and inspect columns", expanded=True):
        preview_tab, schema_tab, quality_tab = st.tabs([
            "Data preview", "Schema", "Data quality"
        ])

        with preview_tab:
            st.dataframe(df.head(100), use_container_width=True, height=320)
            st.download_button(
                "Download cleaned dataset",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name="datamind_cleaned.csv",
                mime="text/csv",
            )

        with schema_tab:
            schema = pd.DataFrame({
                "Column": df.columns,
                "Data type": [str(dtype) for dtype in df.dtypes],
                "Non-null": df.notna().sum().values,
                "Missing": df.isna().sum().values,
                "Unique": df.nunique(dropna=True).values,
            })
            st.dataframe(schema, use_container_width=True)

        with quality_tab:
            quality = pd.DataFrame({
                "Missing values": df.isna().sum(),
                "Missing (%)": (df.isna().mean() * 100).round(2),
                "Unique values": df.nunique(dropna=True),
            }).sort_values("Missing values", ascending=False)
            st.dataframe(quality, use_container_width=True)

# ANSWERS
if submitted:
    if df is None:
        st.warning("Upload a CSV or XLSX dataset before asking questions.")

    elif question.strip():
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown("### Answer")

        safe_question = html.escape(question)

        st.markdown(f"""
        <div style="border-left:3px solid #75BDB4;background:rgba(17,30,45,.8);border-radius:0 12px 12px 0;padding:14px 18px;margin-bottom:12px;">
            <div style="color:#91A8B4;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">YOUR QUESTION</div>
            <div style="color:#E5F0F2;font-size:15px;">{safe_question}</div>
        </div>
        """, unsafe_allow_html=True)

        try:
            with st.spinner("Analyzing your dataset..."):
                answer = answer_question(df, question)
            st.markdown(answer)
        except Exception as exc:
            st.error(f"Could not analyze this question: {exc}")
    else:
        st.info("Type a question in the search bar first.")

# OPTIONAL SNOWFLAKE
with st.expander("Snowflake integration", expanded=False):
    st.markdown(
        "Upload the current dataset to a Snowflake table. "
        "Store credentials in your `.env` file, never directly in this code."
    )

    st.caption(
        "Required: SNOWFLAKE_USER, SNOWFLAKE_PASSWORD, SNOWFLAKE_ACCOUNT, "
        "SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA"
    )

    table_name_input = st.text_input(
        "Destination table name",
        value="DATAMIND_DATA",
    )

    confirm_upload = st.checkbox(
        "I understand that uploading writes this dataset to my Snowflake account."
    )

    if st.button("Connect and upload to Snowflake", type="primary"):
        if df is None:
            st.warning("Upload a dataset before sending it to Snowflake.")
        elif not confirm_upload:
            st.warning("Confirm the upload before continuing.")
        elif not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name_input):
            st.error("Use only letters, numbers, and underscores; the name must not begin with a number.")
        elif not SNOWFLAKE_AVAILABLE:
            st.error("Install the connector with: pip install snowflake-connector-python")
        else:
            conn = None
            try:
                with st.spinner("Connecting to Snowflake..."):
                    conn, connection_error = connect_snowflake()

                    if connection_error:
                        st.error(connection_error)
                    else:
                        success, nchunks, nrows, output = write_pandas(
                            conn,
                            df,
                            table_name_input.upper(),
                            auto_create_table=True,
                            overwrite=False,
                            quote_identifiers=True,
                        )

                        if success:
                            st.success(
                                f"Uploaded {nrows:,} rows to {table_name_input.upper()}."
                            )
                            st.caption(
                                "This creates or appends to a regular Snowflake table. "
                                "Verify your table permissions and account settings."
                            )
                        else:
                            st.error("Snowflake did not confirm a successful upload.")

            except Exception as exc:
                st.error(f"Snowflake upload failed: {exc}")
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass

# FOOTER
st.markdown("""
<div class="footer">
    DataMind · Thoughtful insights for your data
</div>
""", unsafe_allow_html=True)