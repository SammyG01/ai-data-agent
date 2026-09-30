import duckdb
import pandas as pd
import polars as pl
from typing import Dict, Any, Tuple, Optional, List
import os

class DuckDBEngine:
    """
    In-memory or file-backed DuckDB query engine and schema inference wrapper.
    Manages session-level data loading, schema extraction, and SQL execution.
    """
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or ":memory:"
        self.conn = duckdb.connect(database=self.db_path)
        self.table_name = "dataset"
        self.loaded = False
        self.df: Optional[pd.DataFrame] = None
        self.query_history: List[Dict[str, Any]] = []

    def load_file(self, file_path: str) -> Dict[str, Any]:
        """
        Loads CSV or XLSX into DuckDB table `dataset`.
        Returns schema metadata and first 10 rows preview.
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext in [".csv"]:
            self.df = pd.read_csv(file_path)
        elif ext in [".xlsx", ".xls"]:
            self.df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}. Only CSV and XLSX are supported.")

        self.conn.register(self.table_name, self.df)
        self.loaded = True

        return self.get_schema_info()

    def load_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Loads/updates an in-memory or persisted pandas DataFrame into DuckDB."""
        self.df = df.copy()
        self.conn.register(self.table_name, self.df)
        self.loaded = True
        return self.get_schema_info()

    def get_schema_info(self) -> Dict[str, Any]:
        """
        Infers schema, types, row count, column details, and preview rows.
        """
        if not self.loaded or self.df is None:
            raise RuntimeError("No dataset loaded.")

        row_count = len(self.df)
        col_count = len(self.df.columns)

        columns_info = []
        for col in self.df.columns:
            dtype = str(self.df[col].dtype)
            sample_vals = self.df[col].dropna().head(3).tolist()
            if "int" in dtype or "float" in dtype:
                simple_type = "NUMBER"
            elif "datetime" in dtype or "date" in dtype:
                simple_type = "DATE"
            elif "bool" in dtype:
                simple_type = "BOOLEAN"
            else:
                simple_type = "TEXT"

            columns_info.append({
                "name": col,
                "type": simple_type,
                "raw_dtype": dtype,
                "sample_values": sample_vals
            })

        preview_df = self.df.head(10).fillna("")
        preview_records = preview_df.to_dict(orient="records")

        return {
            "table_name": self.table_name,
            "row_count": row_count,
            "col_count": col_count,
            "columns": columns_info,
            "preview": preview_records
        }

    def get_schema_prompt_description(self, semantic_annotations: Optional[Dict[str, Dict[str, str]]] = None) -> Tuple[str, str]:
        """
        Generates schema description and sample rows string formatted specifically
        for Section 7.1 NL-to-SQL System Prompt, enriched with optional semantic annotations.
        """
        if not self.loaded or self.df is None:
            return "", ""

        info = self.get_schema_info()
        schema_lines = [f"Table: {self.table_name}", "Columns:"]
        for col in info["columns"]:
            col_name = col["name"]
            samples = ", ".join([f'"{v}"' if isinstance(v, str) else str(v) for v in col["sample_values"]])
            line = f"- {col_name} ({col['type']}) — e.g. sample values: {samples}"

            # Append semantic data dictionary context if present
            if semantic_annotations and col_name in semantic_annotations:
                ann = semantic_annotations[col_name]
                alias = ann.get("alias")
                desc = ann.get("description")
                unit = ann.get("unit")
                extras = []
                if alias and alias != col_name:
                    extras.append(f"Business Alias: '{alias}'")
                if unit:
                    extras.append(f"Unit: {unit}")
                if desc:
                    extras.append(f"Meaning: {desc}")
                if extras:
                    line += f" [{'; '.join(extras)}]"

            schema_lines.append(line)

        schema_desc = "\n".join(schema_lines)
        sample_rows_df = self.df.head(5)
        sample_rows_str = sample_rows_df.to_csv(index=False)

        return schema_desc, sample_rows_str

    def execute_query(self, sql_query: str) -> pd.DataFrame:
        """
        Executes a SQL query against DuckDB and returns the result dataframe.
        """
        if not self.loaded:
            raise RuntimeError("No dataset loaded in DuckDB engine.")

        result_df = self.conn.execute(sql_query).df()
        self.query_history.append({"query": sql_query})
        return result_df
