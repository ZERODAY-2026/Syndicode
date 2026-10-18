# DataMind

DataMind is a Streamlit data assistant for asking natural-language questions
about Snowflake tables or CSV files. It generates a read-only SQL query, checks
the query against the available schema, executes it, and summarizes the
returned rows. When the result supports a useful visualization, it can also
display a bar, line, or scatter chart.

## Requirements

- Python 3.11 or newer
- [Ollama](https://ollama.com/) running on this computer or reachable on a
  trusted network
- A Snowflake account and a read-enabled role to use Snowflake mode (optional
  for CSV mode)

## Clone and install

Clone the app branch:

```powershell
git clone --branch rustydoctor-datamind-app --single-branch https://github.com/ZERODAY-2026/Syndicode.git
cd Syndicode
```

Create a virtual environment and install Python dependencies. On Windows:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks environment activation, either allow the local activation
script for your user with
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or skip activation and
run `.venv\Scripts\python.exe -m pip install -r requirements.txt` followed by
`.venv\Scripts\streamlit.exe run app.py`.

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Install and start Ollama

Install Ollama from [ollama.com/download](https://ollama.com/download) for your
operating system. Confirm the CLI is available, download the model used by the
app, and verify that it appears in the local model list:

```text
ollama --version
ollama pull gemma3n:e4b
ollama list
```

Ollama normally runs as a background service after installation. If it is not
running, start it in a separate terminal:

```text
ollama serve
```

DataMind connects to `http://127.0.0.1:11434` by default. If Ollama runs at a
different address, set `OLLAMA_HOST` in the same terminal used to launch
Streamlit. For PowerShell:

```powershell
$env:OLLAMA_HOST = "http://127.0.0.1:11434"
```

For macOS/Linux:

```bash
export OLLAMA_HOST=http://127.0.0.1:11434
```

Use a full `http://` or `https://` URL, or `host:port`. If you need Ollama to
listen for another computer on your private network, configure its server
binding as described in the [Ollama FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.md),
then set DataMind's `OLLAMA_HOST` to the Ollama computer's reachable LAN IP,
for example `http://192.168.1.20:11434`. Do not use `0.0.0.0` as the app's
destination address: it is a server bind address, not a remote host address.
The app normalizes a wildcard destination to loopback. Do not expose Ollama
directly to the public internet; use a trusted network, VPN, and appropriate
firewall rules.

## Configure Snowflake (optional)

Create a `.env` file in the repository root, next to `app.py`, with your own
account details. The template below contains placeholders only; replace them
locally and never commit the completed file. `.env` is ignored by Git.

```dotenv
SNOWFLAKE_ACCOUNT=<account-identifier>
SNOWFLAKE_USER=<username>
SNOWFLAKE_PASSWORD=<password>
SNOWFLAKE_WAREHOUSE=<warehouse>
SNOWFLAKE_DATABASE=<database>
SNOWFLAKE_SCHEMA=<schema>
SNOWFLAKE_ROLE=<role>
```

`SNOWFLAKE_ROLE` is optional in the connector, but setting it explicitly makes
the access context predictable. Use your Snowflake account identifier, not
your Snowsight browser URL. Do not put quotes around values unless they are
part of the actual value.

The role needs to use the warehouse, access the selected database and schema,
read the tables, and inspect that database's `INFORMATION_SCHEMA.COLUMNS`.
Check the intended context in a Snowflake worksheet before launching DataMind:

```sql
SELECT CURRENT_ACCOUNT(), CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA();
SHOW TABLES IN SCHEMA <database>.<schema>;
DESC TABLE <database>.<schema>.<table>;
```

If a table is not visible to that role or the current database/schema differs
from the `.env` settings, grant the needed access or correct the local
configuration. Restart Streamlit after changing `.env`.

## Launch the app

From the repository root, with the virtual environment active:

```text
streamlit run app.py
```

Open the local URL printed by Streamlit (usually `http://localhost:8501`).
Choose **Snowflake** or **CSV uploads** in the sidebar, optionally choose a
table or uploaded dataset, then ask a question. The results area shows the
answer, a chart when appropriate, and the returned rows. Generated SQL and
planning details are available under **Query details**.

CSV mode does not require Snowflake credentials. Add one or more CSV files in
the sidebar; filenames become dataset names, with numeric suffixes used when
names collide. The upload limit is configurable per file from 1 to 200 MB
(50 MB by default).

## Data handling and privacy

- CSV files are parsed in memory and queried using a temporary in-memory
  SQLite database. They are not written to Snowflake or saved as uploaded
  files by this app.
- The question, schema, and result rows are sent to the configured Ollama
  endpoint for plan generation and summarization. A remote Ollama server will
  receive these inputs; use a service and network you trust.
- Snowflake mode sends the verified, read-only query to your configured
  Snowflake account.
- Generated plans are written locally to `plans/latest_plan.json`. Local
  `.env`, virtual environments, Python caches, plans, and IDE settings are
  excluded from version control.

## Troubleshooting

| Symptom | Likely cause and next step |
| --- | --- |
| The app says Snowflake settings are missing | Create `.env` in the repository root, check the variable names in the template, and restart Streamlit. Do not paste `.env` contents into logs or issue reports. |
| Snowflake login, warehouse, or authorization error | Verify the account identifier and user; confirm the selected role can use the warehouse and read the database/schema/tables. Run the worksheet checks above using the same role. |
| No tables are available, or the requested table cannot be selected | Check `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`, the role's grants, and table spelling/case. Ensure `INFORMATION_SCHEMA.COLUMNS` is visible to that role. |
| Ollama connection refused or timed out | Start Ollama (`ollama serve` if it is not already running), check the endpoint and port, then set `OLLAMA_HOST` in the same shell used to launch Streamlit. |
| Model not found | Run `ollama pull gemma3n:e4b`, then confirm it appears in `ollama list`. |
| `ollama serve` says the port is already in use | Ollama is likely already running as a background service. Leave it running instead of starting a second server. |
| Ollama works on the same laptop but not from another computer | Use the Ollama laptop's LAN IP as `OLLAMA_HOST`, configure Ollama to listen on a trusted interface, and check private-network firewall rules. Never use `0.0.0.0` as the destination or expose the service publicly. |
| A CSV is rejected or returns no rows | Check that it is a readable CSV with headers and valid encoding, stays below the configured per-file limit, and includes the fields needed by the question. |
| SQL is shown but no results are returned | Review the selected table, role permissions, data filters, and generated SQL under **Query details**. Unsupported questions are reported rather than executed. |
| Streamlit opens on a different port or the default port is occupied | Use the URL printed by Streamlit, or launch with `streamlit run app.py --server.port 8502`. |

## Tests

With the virtual environment active, run the offline unit tests from the
repository root:

```text
python -m unittest discover -s tests -v
```

The tests mock external services; running them does not require Snowflake
credentials or a live Ollama server.
