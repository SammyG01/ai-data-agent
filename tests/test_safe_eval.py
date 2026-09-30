import pandas as pd
import pytest
from app.core.safe_eval import evaluate_safe_expression, SafeEvaluator

def test_safe_arithmetic_evaluation():
    df = pd.DataFrame({"revenue": [100.0, 200.0, 300.0], "cost": [50.0, 80.0, 120.0]})
    # Simple binary operation
    profit = evaluate_safe_expression(df, "revenue - cost")
    assert profit.tolist() == [50.0, 120.0, 180.0]

    # Formula with scalar multiplication and addition
    tax = evaluate_safe_expression(df, "revenue * 0.1 + 5")
    assert tax.tolist() == [15.0, 25.0, 35.0]

def test_safe_functions():
    df = pd.DataFrame({"city": ["lagos", "abuja"], "num": [-10.55, 20.33]})
    upper_city = evaluate_safe_expression(df, "upper(city)")
    assert upper_city.tolist() == ["LAGOS", "ABUJA"]

    abs_num = evaluate_safe_expression(df, "round(abs(num), 1)")
    assert abs_num.tolist() == [10.6, 20.3]

def test_security_rejections():
    df = pd.DataFrame({"a": [1, 2, 3]})
    
    # Block imports
    with pytest.raises(ValueError):
        evaluate_safe_expression(df, "__import__('os').system('ls')")

    # Block exec/eval calls
    with pytest.raises(ValueError):
        evaluate_safe_expression(df, "exec('x=1')")

    # Block dunder access
    with pytest.raises(ValueError):
        evaluate_safe_expression(df, "a.__class__.__base__")
