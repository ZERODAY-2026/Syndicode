import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from src.config import SF_CONFIG

def ingest_dataset(file_path: str, table_name: str = "CUSTOM_DATA"):
    """Reads a CSV or JSON file and uploads it to Snowflake."""
    try:
        # 1. Load data based on file type
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith('.json'):
            df = pd.read_json(file_path)
        else:
            return False, "Unsupported format. Please use .csv or .json"

        # 2. Clean column names
        df.columns = [str(c).replace(' ', '_').replace('-', '_').replace('.', '_').upper() for c in df.columns]

        # 3. Connect using your existing .env credentials
        conn = snowflake.connector.connect(**SF_CONFIG)

        # 4. Upload the data
        success, nchunks, nrows, _ = write_pandas(
            conn=conn,
            df=df,
            table_name=table_name.upper(),
            auto_create_table=True,
            overwrite=True
        )
        conn.close()
        
        if success:
            return True, f"Successfully uploaded {nrows} rows to table {table_name.upper()}"
        else:
            return False, "Failed to upload data."

    except Exception as e:
        return False, str(e)