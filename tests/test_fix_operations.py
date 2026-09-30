import pandas as pd
import pytest
from app.core.fix_operations import (
    remove_duplicate_rows,
    standardize_date_format,
    standardize_text_format,
    fill_missing_value,
    execute_approved_fix
)

def test_remove_duplicate_rows():
    df = pd.DataFrame({"col1": [1, 1, 2], "col2": ["A", "A", "B"]})
    cleaned = remove_duplicate_rows(df)
    assert len(cleaned) == 2

def test_standardize_text_format():
    df = pd.DataFrame({"city": [" Lagos ", "lagos", "LAGOS", "Abuja"]})
    cleaned = standardize_text_format(df, target_column="city", casing="title", strip_whitespace=True)
    assert cleaned["city"].tolist() == ["Lagos", "Lagos", "Lagos", "Abuja"]

def test_fill_missing_value():
    df = pd.DataFrame({"cat": ["A", "A", "B", None]})
    cleaned = fill_missing_value(df, target_column="cat", strategy="most_common")
    assert cleaned["cat"].tolist() == ["A", "A", "B", "A"]

def test_execute_approved_fix_validation():
    df = pd.DataFrame({"a": [1, 2]})
    with pytest.raises(ValueError):
        execute_approved_fix(df, operation_name="eval_arbitrary_code")
