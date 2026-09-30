import pandas as pd
import pytest
from app.core.fix_operations import (
    custom_calculated_column,
    split_column,
    regex_extract,
    replace_value_mapping,
    remove_outliers,
    execute_approved_fix
)

def test_custom_calculated_column():
    df = pd.DataFrame({"price": [10.0, 20.0], "qty": [2, 3]})
    res = custom_calculated_column(df, new_column="total", expression="price * qty")
    assert res["total"].tolist() == [20.0, 60.0]

def test_split_column():
    df = pd.DataFrame({"full_name": ["John Doe", "Jane Smith"]})
    res = split_column(df, target_column="full_name", delimiter=" ", new_columns=["first", "last"])
    assert "first" in res.columns and "last" in res.columns
    assert res["first"].tolist() == ["John", "Jane"]
    assert res["last"].tolist() == ["Doe", "Smith"]

def test_regex_extract():
    df = pd.DataFrame({"order_str": ["ORD-9912-US", "ORD-4421-NG"]})
    res = regex_extract(df, target_column="order_str", pattern=r"\d+", new_column="num")
    assert res["num"].tolist() == ["9912", "4421"]

def test_replace_value_mapping():
    df = pd.DataFrame({"region": ["lagos", "LAG", "Kano"]})
    res = replace_value_mapping(df, target_column="region", mapping={"lagos": "Lagos", "LAG": "Lagos"})
    assert res["region"].tolist() == ["Lagos", "Lagos", "Kano"]

def test_remove_outliers():
    # 10 values with 1 extreme outlier (1000)
    df = pd.DataFrame({"revenue": [10.0, 11.0, 10.5, 12.0, 9.8, 10.2, 11.5, 10.0, 10.8, 1000.0]})
    res = remove_outliers(df, target_column="revenue", factor=1.5)
    assert len(res) == 9
    assert 1000.0 not in res["revenue"].values
