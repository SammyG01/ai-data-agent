import os
import pandas as pd
import pytest
from app.core.engine import DuckDBEngine
from app.core.cleaning import detect_data_quality_issues

SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "..", "sample_data", "sales_data.csv")

def test_engine_schema_and_query():
    engine = DuckDBEngine()
    schema_info = engine.load_file(SAMPLE_CSV)

    assert schema_info["table_name"] == "dataset"
    assert schema_info["row_count"] > 0
    assert len(schema_info["columns"]) == 6

    # Test SELECT query execution
    df_result = engine.execute_query("SELECT region, SUM(revenue) as total_rev FROM dataset GROUP BY region")
    assert isinstance(df_result, pd.DataFrame)
    assert "total_rev" in df_result.columns

def test_data_quality_detection():
    engine = DuckDBEngine()
    engine.load_file(SAMPLE_CSV)
    df = engine.df

    report = detect_data_quality_issues(df)
    assert report["total_rows"] == 11
    assert report["total_issues"] > 0

    issue_types = [item["issue_type"] for item in report["issues"]]
    assert "duplicate_rows" in issue_types
    assert "missing_values" in issue_types
    assert "inconsistent_formatting" in issue_types
