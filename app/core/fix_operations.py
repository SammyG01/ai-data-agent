import pandas as pd
import numpy as np
import re
from typing import Dict, Any, Optional, List
from app.core.safe_eval import evaluate_safe_expression

def remove_duplicate_rows(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Removes exact duplicate rows from dataframe."""
    cleaned = df.drop_duplicates().reset_index(drop=True)
    return cleaned

def standardize_date_format(df: pd.DataFrame, target_column: str, target_format: str = "%Y-%m-%d", **kwargs) -> pd.DataFrame:
    """Standardizes date strings in target_column to uniform format (e.g. YYYY-MM-DD)."""
    cleaned = df.copy()
    if target_column not in cleaned.columns:
        return cleaned

    # Convert to datetime using flexible pandas parsing
    parsed_dates = pd.to_datetime(cleaned[target_column], errors="coerce")

    # Map format string if short forms used
    format_map = {
        "YYYY-MM-DD": "%Y-%m-%d",
        "DD/MM/YYYY": "%d/%m/%Y",
        "MM/DD/YYYY": "%m/%d/%Y",
        "YYYY/MM/DD": "%Y/%m/%d"
    }
    actual_fmt = format_map.get(target_format, target_format)

    cleaned[target_column] = parsed_dates.dt.strftime(actual_fmt).fillna(cleaned[target_column])
    return cleaned

def standardize_text_format(df: pd.DataFrame, target_column: str, casing: str = "title", strip_whitespace: bool = True, **kwargs) -> pd.DataFrame:
    """Standardizes text casing and strips leading/trailing whitespace in target_column."""
    cleaned = df.copy()
    if target_column not in cleaned.columns:
        return cleaned

    series = cleaned[target_column].astype(str)

    if strip_whitespace:
        series = series.str.strip()

    if casing == "title":
        series = series.str.title()
    elif casing == "lower":
        series = series.str.lower()
    elif casing == "upper":
        series = series.str.upper()

    cleaned[target_column] = series
    return cleaned

def fill_missing_value(df: pd.DataFrame, target_column: str, strategy: str = "most_common", fixed_value: Optional[Any] = None, **kwargs) -> pd.DataFrame:
    """Fills missing values in target_column based on strategy ('most_common', 'fixed_value', or 'blank')."""
    cleaned = df.copy()
    if target_column not in cleaned.columns:
        return cleaned

    if strategy == "most_common":
        mode_val = cleaned[target_column].dropna().mode()
        fill_val = mode_val.iloc[0] if not mode_val.empty else ""
    elif strategy == "fixed_value":
        fill_val = fixed_value if fixed_value is not None else ""
    elif strategy == "blank":
        fill_val = ""
    else:
        fill_val = fixed_value or ""

    cleaned[target_column] = cleaned[target_column].fillna(fill_val)
    if cleaned[target_column].dtype == "object" or "str" in str(cleaned[target_column].dtype).lower():
        cleaned[target_column] = cleaned[target_column].replace(r'^\s*$', fill_val, regex=True)

    return cleaned

# --- ADVANCED EXPANDED OPERATIONS ---

def custom_calculated_column(df: pd.DataFrame, new_column: str, expression: str, **kwargs) -> pd.DataFrame:
    """
    Safely calculates a new column using AST expression evaluation.
    Example: new_column="profit", expression="revenue * 0.20"
    """
    cleaned = df.copy()
    result_series = evaluate_safe_expression(cleaned, expression)
    target_col = new_column if new_column else "calc_col"
    cleaned[target_col] = result_series
    return cleaned

def regex_extract(df: pd.DataFrame, target_column: str, pattern: str, new_column: Optional[str] = None, **kwargs) -> pd.DataFrame:
    """
    Extracts matches of a regex pattern from target_column into a new or replaced column.
    """
    cleaned = df.copy()
    if target_column not in cleaned.columns:
        return cleaned

    extracted = cleaned[target_column].astype(str).str.extract(f"({pattern})")[0]
    out_col = new_column if new_column else f"{target_column}_extracted"
    cleaned[out_col] = extracted
    return cleaned

def split_column(df: pd.DataFrame, target_column: str, delimiter: str = " ", new_columns: Optional[List[str]] = None, **kwargs) -> pd.DataFrame:
    """
    Splits a delimited text column into multiple distinct columns.
    Example: 'John Doe' -> 'first_name', 'last_name'
    """
    cleaned = df.copy()
    if target_column not in cleaned.columns:
        return cleaned

    split_series = cleaned[target_column].astype(str).str.split(delimiter, expand=True)
    num_splits = split_series.shape[1]

    if new_columns and len(new_columns) == num_splits:
        col_names = new_columns
    else:
        col_names = [f"{target_column}_{i+1}" for i in range(num_splits)]

    for idx, col_name in enumerate(col_names):
        cleaned[col_name] = split_series[idx].str.strip()

    return cleaned

def replace_value_mapping(df: pd.DataFrame, target_column: str, mapping: Dict[str, Any], **kwargs) -> pd.DataFrame:
    """
    Replaces values in target_column based on a dictionary mapping.
    Example: mapping={'lagos': 'Lagos', 'LAG': 'Lagos'}
    """
    cleaned = df.copy()
    if target_column not in cleaned.columns:
        return cleaned

    cleaned[target_column] = cleaned[target_column].replace(mapping)
    return cleaned

def remove_outliers(df: pd.DataFrame, target_column: str, factor: float = 1.5, **kwargs) -> pd.DataFrame:
    """
    Filters out numeric outliers using the Interquartile Range (IQR) rule.
    """
    cleaned = df.copy()
    if target_column not in cleaned.columns or not pd.api.types.is_numeric_dtype(cleaned[target_column]):
        return cleaned

    q25 = cleaned[target_column].quantile(0.25)
    q75 = cleaned[target_column].quantile(0.75)
    iqr = q75 - q25
    lower_bound = q25 - (factor * iqr)
    upper_bound = q75 + (factor * iqr)

    return cleaned[(cleaned[target_column] >= lower_bound) & (cleaned[target_column] <= upper_bound)].reset_index(drop=True)

# Registry of supported fix operations
SUPPORTED_OPERATIONS = {
    "remove_duplicate_rows": remove_duplicate_rows,
    "standardize_date_format": standardize_date_format,
    "standardize_text_format": standardize_text_format,
    "fill_missing_value": fill_missing_value,
    "custom_calculated_column": custom_calculated_column,
    "regex_extract": regex_extract,
    "split_column": split_column,
    "replace_value_mapping": replace_value_mapping,
    "remove_outliers": remove_outliers
}

def execute_approved_fix(df: pd.DataFrame, operation_name: str, target_column: Optional[str] = None, parameters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    Executes a human-approved fix operation.
    Validates operation against fixed set of pre-written functions.
    Never evals dynamic code.
    """
    if operation_name not in SUPPORTED_OPERATIONS:
        raise ValueError(f"Unsupported operation type: '{operation_name}'. Must be one of {list(SUPPORTED_OPERATIONS.keys())}")

    func = SUPPORTED_OPERATIONS[operation_name]
    params = parameters or {}

    return func(df, target_column=target_column, **params)
