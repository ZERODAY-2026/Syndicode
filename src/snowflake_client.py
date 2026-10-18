import snowflake.connector
from src.config import SF_CONFIG

def get_schema_metadata():
    conn = snowflake.connector.connect(**SF_CONFIG)
    cursor = conn.cursor()
    try:
        # Dynamically get the schema from the .env file
        schema_name = SF_CONFIG["schema"]
        db_name = SF_CONFIG["database"]
        
        query = f"""
            SELECT table_name, column_name, data_type 
            FROM {db_name}.INFORMATION_SCHEMA.COLUMNS 
            WHERE table_schema = '{schema_name}'
        """
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def execute_sql(query: str) -> dict:
    conn = snowflake.connector.connect(**SF_CONFIG)
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        return {
            "query_id": cursor.sfqid,
            "columns": [desc[0] for desc in cursor.description],
            "rows": cursor.fetchall()
        }
    finally:
        cursor.close()
        conn.close()