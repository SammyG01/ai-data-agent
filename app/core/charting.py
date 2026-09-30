import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, Any, Tuple, Optional

def infer_chart_type(df: pd.DataFrame) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Implements heuristic rules from Section 5 of Project Brief:
    - One date/time column + one numeric column -> Line chart
    - One categorical column + one numeric column -> Bar chart
    - One categorical column with proportions (% of total) -> Pie chart
    - Two numeric columns -> Scatter plot
    - Single numeric value -> Big number / Metric display
    - More than 2 dimensions, or ambiguous -> Table only (no auto-chart)

    Returns: (chart_type, x_col, y_col)
    """
    if df is None or df.empty:
        return "table", None, None

    cols = list(df.columns)
    num_cols = len(cols)
    num_rows = len(df)

    # 1. Single numeric value (1 row, 1 numeric col)
    if num_rows == 1 and num_cols == 1 and pd.api.types.is_numeric_dtype(df[cols[0]]):
        return "metric", cols[0], None

    if num_cols == 2:
        col1, col2 = cols[0], cols[1]
        dtype1 = df[col1].dtype
        dtype2 = df[col2].dtype

        is_num1 = pd.api.types.is_numeric_dtype(dtype1)
        is_num2 = pd.api.types.is_numeric_dtype(dtype2)

        is_date1 = "datetime" in str(dtype1).lower() or "date" in str(dtype1).lower() or "year" in col1.lower()
        is_date2 = "datetime" in str(dtype2).lower() or "date" in str(dtype2).lower() or "year" in col2.lower()

        # Date/Time + Numeric -> Line chart
        if (is_date1 and is_num2):
            return "line", col1, col2
        if (is_date2 and is_num1):
            return "line", col2, col1

        # Two Numeric -> Scatter plot
        if is_num1 and is_num2:
            return "scatter", col1, col2

        # Categorical + Proportions/Percentages -> Pie chart
        if not is_num1 and is_num2:
            # Check if values look like proportions (sum ~100 or ~1)
            y_sum = df[col2].sum()
            if "share" in col2.lower() or "percent" in col2.lower() or "proportion" in col2.lower() or abs(y_sum - 100) < 1.0 or abs(y_sum - 1.0) < 0.05:
                return "pie", col1, col2
            return "bar", col1, col2

        if is_num1 and not is_num2:
            return "bar", col2, col1

    # Fallback for ambiguous or multi-column results
    return "table", None, None

def generate_plotly_figure(df: pd.DataFrame, chart_type: str, x_col: Optional[str] = None, y_col: Optional[str] = None) -> Optional[go.Figure]:
    """
    Generates a Plotly figure object based on dataset and specified chart_type.
    Supports manual overrides: 'line', 'bar', 'pie', 'scatter', 'metric', 'table'.
    """
    if df is None or df.empty or chart_type == "table":
        return None

    cols = list(df.columns)
    if not x_col and len(cols) > 0:
        x_col = cols[0]
    if not y_col and len(cols) > 1:
        y_col = cols[1]

    try:
        if chart_type == "metric":
            val = df.iloc[0, 0]
            col_name = cols[0]
            fig = go.Figure(go.Indicator(
                mode="number",
                value=float(val) if isinstance(val, (int, float)) else None,
                title={"text": col_name},
                number={"valueformat": ",.2f" if isinstance(val, float) else ",d"}
            ))
            fig.update_layout(height=250)
            return fig

        elif chart_type == "line":
            fig = px.line(df, x=x_col, y=y_col, title=f"{y_col} by {x_col}", markers=True)
            fig.update_layout(template="plotly_white")
            return fig

        elif chart_type == "bar":
            fig = px.bar(df, x=x_col, y=y_col, title=f"{y_col} by {x_col}", text_auto=True)
            fig.update_layout(template="plotly_white")
            return fig

        elif chart_type == "pie":
            fig = px.pie(df, names=x_col, values=y_col, title=f"Distribution of {y_col} by {x_col}")
            return fig

        elif chart_type == "scatter":
            fig = px.scatter(df, x=x_col, y=y_col, title=f"{y_col} vs {x_col}")
            fig.update_layout(template="plotly_white")
            return fig

    except Exception:
        return None

    return None
