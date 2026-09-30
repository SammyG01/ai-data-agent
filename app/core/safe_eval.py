import ast
import operator
import pandas as pd
import numpy as np
from typing import Any, Dict

# Whitelist of safe binary operations
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

# Whitelist of safe unary operations
SAFE_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

# Whitelist of safe scalar / series functions
SAFE_FUNCTIONS = {
    "round": lambda x, n=0: x.round(n) if hasattr(x, "round") else round(x, n),
    "abs": lambda x: x.abs() if hasattr(x, "abs") else abs(x),
    "upper": lambda x: x.str.upper() if hasattr(x, "str") else str(x).upper(),
    "lower": lambda x: x.str.lower() if hasattr(x, "str") else str(x).lower(),
    "strip": lambda x: x.str.strip() if hasattr(x, "str") else str(x).strip(),
    "len": lambda x: x.str.len() if hasattr(x, "str") else len(x),
    "int": lambda x: x.astype(int) if hasattr(x, "astype") else int(x),
    "float": lambda x: x.astype(float) if hasattr(x, "astype") else float(x),
    "str": lambda x: x.astype(str) if hasattr(x, "astype") else str(x),
}

class SafeEvaluator(ast.NodeVisitor):
    """
    Evaluates safe arithmetic and string expressions against a pandas DataFrame.
    Strictly forbids arbitrary code execution, dunder access, imports, and system calls.
    """
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def evaluate(self, expr_str: str) -> Any:
        try:
            parsed = ast.parse(expr_str.strip(), mode="eval")
        except SyntaxError as e:
            raise ValueError(f"Syntax error in formula: {str(e)}")
        return self.visit(parsed.body)

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        left = self.visit(node.left)
        right = self.visit(node.right)
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ValueError(f"Operator {op_type.__name__} is not allowed.")
        return SAFE_OPERATORS[op_type](left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        operand = self.visit(node.operand)
        op_type = type(node.op)
        if op_type not in SAFE_UNARY_OPERATORS:
            raise ValueError(f"Unary operator {op_type.__name__} is not allowed.")
        return SAFE_UNARY_OPERATORS[op_type](operand)

    def visit_Compare(self, node: ast.Compare) -> Any:
        left = self.visit(node.left)
        result = None
        for op, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            op_type = type(op)
            if op_type not in SAFE_OPERATORS:
                raise ValueError(f"Comparison operator {op_type.__name__} is not allowed.")
            cmp_res = SAFE_OPERATORS[op_type](left, right)
            result = cmp_res if result is None else (result & cmp_res)
            left = right
        return result

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only whitelisted top-level functions are supported.")
        func_name = node.func.id.lower()
        if func_name not in SAFE_FUNCTIONS:
            raise ValueError(f"Function '{func_name}' is not permitted. Allowed: {list(SAFE_FUNCTIONS.keys())}")

        args = [self.visit(arg) for arg in node.args]
        return SAFE_FUNCTIONS[func_name](*args)

    def visit_Name(self, node: ast.Name) -> Any:
        col_name = node.id
        if col_name in self.df.columns:
            return self.df[col_name]
        elif col_name.lower() in [c.lower() for c in self.df.columns]:
            # Case-insensitive column match
            actual = next(c for c in self.df.columns if c.lower() == col_name.lower())
            return self.df[actual]
        elif col_name.lower() == "true":
            return True
        elif col_name.lower() == "false":
            return False
        elif col_name.lower() == "none":
            return None
        else:
            raise ValueError(f"Column '{col_name}' does not exist in dataset.")

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def generic_visit(self, node: ast.AST) -> Any:
        raise ValueError(f"AST element '{type(node).__name__}' is strictly disallowed for security.")

def evaluate_safe_expression(df: pd.DataFrame, expression: str) -> pd.Series:
    """
    Safely evaluates a formula expression against columns of a dataframe.
    Example: evaluate_safe_expression(df, "revenue * 1.15")
    """
    evaluator = SafeEvaluator(df)
    result = evaluator.evaluate(expression)
    if isinstance(result, (int, float, str, bool)):
        result = pd.Series([result] * len(df), index=df.index)
    return result
