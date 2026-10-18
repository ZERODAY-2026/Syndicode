# DataMind

DataMind is a Streamlit data assistant that turns natural-language questions into
SQL, checks the generated query against the available schema, runs it, and
summarizes the returned data. It supports Snowflake tables and CSV files
uploaded for the current app session.

## Requirements

- Python 3.10 or newer
- [Ollama](https://ollama.com/) running a compatible local or reachable service
- A Snowflake account and credentials when using the Snowflake data source

## Installation

Create and activate a virtual environment, then install the project dependencies:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Pull the model used by the app and make sure Ollama is running:

```powershell
ollama pull gemma3n:e4b
ollama serve
```

The default Ollama endpoint is `http://127.0.0.1:11434`. To use a different
endpoint, set `OLLAMA_HOST` in the environment before starting the app. It may
be an HTTP(S) URL or a `host:port` value.

## Snowflake configuration

Create a `.env` file in the repository root for Snowflake mode. Do not commit
this file; it is ignored by Git.

```dotenv
SNOWFLAKE_ACCOUNT=<account-identifier>
SNOWFLAKE_USER=<username>
SNOWFLAKE_PASSWORD=<password>
SNOWFLAKE_WAREHOUSE=<warehouse>
SNOWFLAKE_DATABASE=<database>
SNOWFLAKE_SCHEMA=<schema>
SNOWFLAKE_ROLE=<role>
```

The configured Snowflake user needs access to the warehouse, database, schema,
and tables it should query, including permission to inspect the schema's
`INFORMATION_SCHEMA.COLUMNS`. `SNOWFLAKE_ROLE` should be set to a role with
those grants.

## Run

From the repository root, start the app with:

```powershell
streamlit run app.py
```

Open the local URL printed by Streamlit. Choose **Snowflake** to query the
configured schema, optionally enter a table name, and submit a question. Choose
**Upload CSV files** to query one or more CSVs instead; filenames are converted
to SQL table names, and duplicate names get a numeric suffix. For either source,
the app displays the answer, generated plan, executed SQL, and query results.

## CSV handling and privacy

Uploaded CSVs are loaded into memory and queried using a temporary, in-memory
SQLite database. They are not written to Snowflake or saved by the app as
uploaded files. Uploads are scoped to the current Streamlit browser session,
and each file has a configurable size limit (50 MB by default, up to 200 MB).

The question, schema, and returned query data are sent to the configured Ollama
endpoint for planning or summarization. If `OLLAMA_HOST` points to a remote
service, that service will receive those inputs. Snowflake mode sends the
verified SQL to the configured Snowflake account. Generated plans are written
to `plans/latest_plan.json`; this runtime output and local configuration are
excluded from version control.

## Tests

Run the unit tests from the repository root:

```powershell
python -m unittest discover -s tests -v
```
