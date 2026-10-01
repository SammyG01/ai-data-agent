import re
import urllib.parse
import pandas as pd
from typing import Tuple, Optional, Dict, Any

def parse_google_sheets_url(url: str) -> str:
    """
    Transforms standard Google Sheet sharing/view URLs into direct CSV export URLs.
    Example:
    https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit?usp=sharing
    ->
    https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/export?format=csv
    """
    clean_url = url.strip()
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", clean_url)
    if not match:
        raise ValueError("Invalid Google Sheets URL. URL must contain '/spreadsheets/d/<sheet_id>'.")

    sheet_id = match.group(1)

    # Extract gid (tab identifier) if present
    gid_match = re.search(r"[#&?]gid=([0-9]+)", clean_url)
    gid = gid_match.group(1) if gid_match else "0"

    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    return export_url

def load_google_sheet(url: str) -> Tuple[pd.DataFrame, str]:
    """
    Downloads and parses a Google Sheet directly into a pandas DataFrame.
    Returns (DataFrame, sheet_title_or_id).
    """
    export_url = parse_google_sheets_url(url)
    try:
        df = pd.read_csv(export_url)
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
        sheet_id = match.group(1) if match else "google_sheet"
        return df, f"Google_Sheet_{sheet_id[:8]}"
    except Exception as e:
        raise RuntimeError(
            f"Failed to fetch Google Sheet: {str(e)}. "
            "Please ensure the Google Sheet link sharing is set to 'Anyone with the link can view'."
        )

def load_sql_database(connection_url: str, table_or_query: str) -> Tuple[pd.DataFrame, str]:
    """
    Loads data from an external SQL database (SQLite, PostgreSQL, MySQL) into a pandas DataFrame.
    """
    try:
        import sqlalchemy
        engine = sqlalchemy.create_engine(connection_url)
        # Check if table or query
        clean_target = table_or_query.strip()
        if clean_target.upper().startswith("SELECT"):
            df = pd.read_sql_query(clean_target, engine)
            source_name = "SQL_Query_Result"
        else:
            df = pd.read_sql_table(clean_target, engine)
            source_name = f"SQL_Table_{clean_target}"
        return df, source_name
    except Exception as e:
        raise RuntimeError(f"Database connection failed: {str(e)}")
