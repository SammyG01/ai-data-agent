import re
from typing import Dict, Any, List, Optional
import pandas as pd

DEFAULT_SEMANTIC_RULES = {
    "rev": {"alias": "Revenue", "unit": "Naira (₦) / Currency", "description": "Total sales revenue amount generated"},
    "sales": {"alias": "Sales", "unit": "Naira (₦) / Currency", "description": "Gross sales value"},
    "cost": {"alias": "Cost", "unit": "Naira (₦) / Currency", "description": "Expenses or purchase cost"},
    "profit": {"alias": "Profit", "unit": "Naira (₦) / Currency", "description": "Net income (revenue minus expenses)"},
    "date": {"alias": "Date", "unit": "Timestamp", "description": "Transaction or recording date"},
    "reg": {"alias": "Region", "unit": "Geographic Zone", "description": "Geographical sales territory or branch location"},
    "cust": {"alias": "Customer", "unit": "Identifier / Name", "description": "Customer name or unique account identifier"},
    "prod": {"alias": "Product", "unit": "Category / Item", "description": "Product name or merchandise category"},
    "qty": {"alias": "Quantity", "unit": "Units count", "description": "Number of units or items purchased"},
    "id": {"alias": "ID", "unit": "Identifier", "description": "Unique key or transaction record identifier"}
}

def auto_infer_column_metadata(col_name: str, sample_series: pd.Series) -> Dict[str, str]:
    """
    Infers sensible default business aliases and descriptions from column names and data types.
    """
    cleaned_name = col_name.lower().replace("_", " ")
    alias = col_name.replace("_", " ").title()
    desc = f"Values representing {cleaned_name}"
    unit = "Text"

    dtype_str = str(sample_series.dtype).lower()
    if "int" in dtype_str or "float" in dtype_str:
        unit = "Number"
    elif "date" in dtype_str or "datetime" in dtype_str:
        unit = "Date"

    for key, rule in DEFAULT_SEMANTIC_RULES.items():
        if key in cleaned_name:
            alias = rule["alias"]
            unit = rule["unit"]
            desc = rule["description"]
            break

    return {
        "alias": alias,
        "description": desc,
        "unit": unit
    }

class DataDictionary:
    """
    Maintains semantic data dictionary annotations for a dataset.
    Translates raw column names into domain-specific business terminology.
    """
    def __init__(self, initial_annotations: Optional[Dict[str, Dict[str, str]]] = None):
        self.annotations: Dict[str, Dict[str, str]] = initial_annotations or {}

    def initialize_from_df(self, df: pd.DataFrame):
        for col in df.columns:
            if col not in self.annotations:
                self.annotations[col] = auto_infer_column_metadata(col, df[col])

    def update_column(self, col_name: str, alias: Optional[str] = None, description: Optional[str] = None, unit: Optional[str] = None):
        if col_name not in self.annotations:
            self.annotations[col_name] = {"alias": col_name, "description": "", "unit": ""}
        if alias is not None:
            self.annotations[col_name]["alias"] = alias
        if description is not None:
            self.annotations[col_name]["description"] = description
        if unit is not None:
            self.annotations[col_name]["unit"] = unit

    def get_all(self) -> Dict[str, Dict[str, str]]:
        return self.annotations

class FewShotMemory:
    """
    Stores verified Natural Language Question -> DuckDB SQL query examples.
    Formats examples for injection into the Claude prompt to drastically reduce NL-to-SQL brittleness.
    """
    def __init__(self, seed_examples: Optional[List[Dict[str, str]]] = None):
        self.examples: List[Dict[str, str]] = seed_examples or []

    def add_verified_query(self, question: str, sql: str):
        # Prevent exact duplicates
        for ex in self.examples:
            if ex["question"].strip().lower() == question.strip().lower():
                ex["sql"] = sql
                return
        self.examples.append({"question": question.strip(), "sql": sql.strip()})

    def format_prompt_examples(self, limit: int = 4) -> str:
        """Formats top few-shot examples for LLM prompt context."""
        if not self.examples:
            return ""
        
        lines = ["\nVerified Query Examples for this dataset:"]
        for ex in self.examples[-limit:]:
            lines.append(f"Q: {ex['question']}")
            lines.append(f"SQL: {ex['sql']}\n")
        return "\n".join(lines)
