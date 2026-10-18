import snowflake.connector
from src.config import SF_CONFIG

def get_schema_metadata():
    conn = snowflake.connector.connect(**SF_CONFIG)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT table_name, column_name, data_type 
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE table_schema = %s
            ORDER BY table_name, ordinal_position
        """, (SF_CONFIG["schema"],))
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
