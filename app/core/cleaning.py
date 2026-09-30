import pandas as pd
import polars as pl
import re
from typing import Dict, Any, List

def is_string_dtype(series: pd.Series) -> bool:
    """Helper to check if a pandas series has a string/object data type."""
    dtype_str = str(series.dtype).lower()
    return "str" in dtype_str or "object" in dtype_str or isinstance(series.dtype, pd.StringDtype)

def detect_data_quality_issues(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Executes rule-based heuristics to detect data quality flags as specified in Section 6:
    1. Duplicates: exact duplicate rows.
    2. Missing values: null/blank count and percentage per column.
    3. Inconsistent formatting: date format mixing, text casing inconsistency, leading/trailing whitespace.
    """
    total_rows = len(df)
    if total_rows == 0:
        return {
            "total_rows": 0,
            "issues": [],
            "summary": "Dataset is empty."
        }

    issues: List[Dict[str, Any]] = []

    # 1. Duplicate Rows Detection
    duplicate_mask = df.duplicated(keep=False)
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        dup_indices = df[duplicate_mask].index.tolist()[:10]  # preview first 10
        issues.append({
            "issue_type": "duplicate_rows",
            "title": "Duplicate Rows Found",
            "count": dup_count,
            "affected_columns": list(df.columns),
            "sample_row_indices": dup_indices,
            "description": f"Found {dup_count} exact duplicate row(s) out of {total_rows} total rows."
        })

    # 2. Missing/Blank Values Detection
    missing_by_col = {}
    for col in df.columns:
        # Consider NaNs, Nones, and whitespace-only strings as missing
        col_series = df[col]
        null_mask = col_series.isna()
        if is_string_dtype(col_series):
            blank_str_mask = col_series.astype(str).str.strip().eq("")
            null_mask = null_mask | blank_str_mask

        missing_cnt = int(null_mask.sum())
        if missing_cnt > 0:
            missing_pct = round((missing_cnt / total_rows) * 100, 2)
            missing_by_col[col] = {
                "count": missing_cnt,
                "percentage": missing_pct
            }

    if missing_by_col:
        issues.append({
            "issue_type": "missing_values",
            "title": "Missing / Blank Values",
            "columns": missing_by_col,
            "affected_columns": list(missing_by_col.keys()),
            "description": f"Missing values detected across {len(missing_by_col)} column(s)."
        })

    # 3. Inconsistent Formatting Detection (Dates & Text)
    formatting_issues = []
    for col in df.columns:
        col_series = df[col].dropna()
        if len(col_series) == 0:
            continue

        if is_string_dtype(col_series):
            str_vals = col_series.astype(str)

            # Check leading/trailing whitespace
            has_whitespace = (str_vals != str_vals.str.strip()).any()

            # Check casing inconsistencies (e.g. Lagos vs lagos vs LAGOS)
            lower_vals = str_vals.str.strip().str.lower()
            unique_raw = str_vals.str.strip().nunique()
            unique_lower = lower_vals.nunique()

            # If lowercase grouping reduces unique count, casing varies
            has_casing_inconsistency = (unique_raw > unique_lower)

            if has_whitespace or has_casing_inconsistency:
                reasons = []
                if has_whitespace:
                    reasons.append("unstripped whitespace")
                if has_casing_inconsistency:
                    reasons.append("mixed casing (e.g. Lagos vs lagos)")

                formatting_issues.append({
                    "column": col,
                    "type": "text_format",
                    "reasons": reasons,
                    "sample_unique_values": str_vals.unique()[:5].tolist()
                })

            # Check date format mixing
            sample_str = col_series.astype(str).head(30)
            date_patterns = set()
            for val in sample_str:
                val_clean = val.strip()
                if re.match(r'^\d{4}-\d{2}-\d{2}$', val_clean):
                    date_patterns.add("YYYY-MM-DD")
                elif re.match(r'^\d{2}/\d{2}/\d{4}$', val_clean):
                    date_patterns.add("DD/MM/YYYY")
                elif re.match(r'^\d{2}-\d{2}-\d{4}$', val_clean):
                    date_patterns.add("DD-MM-YYYY")
                elif re.match(r'^[A-Za-z]{3}\s+\d{1,2},\s+\d{4}$', val_clean):
                    date_patterns.add("MMM DD, YYYY")

            if len(date_patterns) > 1:
                formatting_issues.append({
                    "column": col,
                    "type": "date_format",
                    "detected_patterns": list(date_patterns),
                    "reasons": [f"Mixed date formats detected: {', '.join(date_patterns)}"]
                })

    if formatting_issues:
        issues.append({
            "issue_type": "inconsistent_formatting",
            "title": "Inconsistent Column Formatting",
            "details": formatting_issues,
            "affected_columns": list(set([item["column"] for item in formatting_issues])),
            "description": f"Inconsistent formatting found in {len(formatting_issues)} column(s)."
        })

    return {
        "total_rows": total_rows,
        "total_issues": len(issues),
        "issues": issues
    }
