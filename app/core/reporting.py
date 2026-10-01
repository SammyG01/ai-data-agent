import os
import json
from typing import Dict, Any, Optional
import pandas as pd
from openai import OpenAI

REPORT_PROMPT_TEMPLATE = """You are an elite Chief Data Officer and executive business advisor.
Analyze the following dataset profile, metrics summary, and data quality audit, and generate a high-impact, polished Executive Briefing.

Dataset Overview:
- Source Name: {dataset_name}
- Total Records: {total_rows}
- Columns: {columns}
- Numeric Metrics Summary:
{numeric_summary}
- Categorical Distributions:
{categorical_summary}

Data Quality Audit Findings:
- Total Hygiene Issues Flagged: {total_issues}
- Issue Details: {quality_issues_json}

Generate a concise, decision-ready Executive Digest formatted in clear GitHub Markdown using these exact sections:

### 1. 🏢 Executive Summary
A 2-3 sentence high-level overview explaining what this dataset represents, the overall operational scale, and the primary business takeaway.

### 2. 📊 Key Performance Indicators (KPIs) & Drivers
- Highlight 3 to 4 core financial or operational metrics (totals, averages, top performing entities).
- Explain what is driving performance.

### 3. 🛡️ Data Health & Operational Risk Assessment
- Explicitly review the data quality audit findings (missing values, duplicates, formatting inconsistencies).
- Quantify the risk of making business decisions on uncleaned records.

### 4. 🎯 Strategic Management Recommendations
Provide 3 bullet points with direct, practical next steps that executive leadership or operations teams should implement immediately.

Keep the tone professional, objective, and executive-friendly. Do not include markdown preamble outside the document."""

def generate_dataset_profile(df: pd.DataFrame) -> Dict[str, Any]:
    """Extracts summary statistics for LLM reporting context."""
    num_cols = df.select_dtypes(include=['number']).columns.tolist()
    cat_cols = df.select_dtypes(include=['object', 'string', 'category']).columns.tolist()

    numeric_summary = {}
    for col in num_cols[:6]: # Limit to top 6 numeric columns
        s = df[col].dropna()
        if not s.empty:
            numeric_summary[col] = {
                "total": float(s.sum()),
                "mean": round(float(s.mean()), 2),
                "min": float(s.min()),
                "max": float(s.max())
            }

    categorical_summary = {}
    for col in cat_cols[:4]: # Limit to top 4 categorical columns
        top_vals = df[col].value_counts().head(3).to_dict()
        categorical_summary[col] = {str(k): int(v) for k, v in top_vals.items()}

    return {
        "columns": list(df.columns),
        "total_rows": len(df),
        "numeric_summary": numeric_summary,
        "categorical_summary": categorical_summary
    }

def generate_executive_digest(
    df: pd.DataFrame,
    quality_report: Dict[str, Any],
    dataset_name: str = "Active Dataset",
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> str:
    """Generates an executive briefing using OpenAI."""
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    profile = generate_dataset_profile(df)

    if not api_key:
        # Fallback heuristic summary if API key is not configured
        return f"""### 1. 🏢 Executive Summary
The dataset **{dataset_name}** contains **{len(df):,} records** across **{len(df.columns)} columns**.

### 2. 📊 Key Performance Indicators (KPIs)
- **Total Record Count**: {len(df):,} entries
- **Numeric Fields Profiled**: {len(profile['numeric_summary'])} metrics analyzed.
{chr(10).join([f"- **{k}**: Total = {v['total']:,.2f}, Avg = {v['mean']:,.2f}" for k, v in profile['numeric_summary'].items()])}

### 3. 🛡️ Data Health & Operational Risk Assessment
- Flagged Issues: **{quality_report.get('total_issues', 0)}** data hygiene anomalies.
- Recommended Action: Review and apply pending fixes in Data Entry mode before running board-level reports.

### 4. 🎯 Strategic Management Recommendations
1. Standardize formatting and eliminate duplicate rows to ensure reporting accuracy.
2. Monitor key financial metrics on a weekly schedule.
3. Configure semantic definitions for raw database abbreviations."""

    client = OpenAI(api_key=api_key)
    prompt = REPORT_PROMPT_TEMPLATE.format(
        dataset_name=dataset_name,
        total_rows=len(df),
        columns=", ".join(df.columns),
        numeric_summary=json.dumps(profile["numeric_summary"], indent=2),
        categorical_summary=json.dumps(profile["categorical_summary"], indent=2),
        total_issues=quality_report.get("total_issues", 0),
        quality_issues_json=json.dumps(quality_report.get("issues", [])[:4], indent=2)
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an executive business analyst and Chief Data Officer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    return response.choices[0].message.content or ""

def generate_report_html(markdown_content: str, dataset_name: str) -> str:
    """Formats markdown briefing into a self-contained, printable executive HTML document."""
    import html
    # Simple conversion of markdown headers and bolding
    body_html = html.escape(markdown_content).replace("\n", "<br>")
    # Re-enable basic headers and bolding
    body_html = body_html.replace("&lt;h3&gt;", "<h3>").replace("&lt;/h3&gt;", "</h3>")
    body_html = body_html.replace("### ", "<h3>").replace("&lt;br&gt;&lt;br&gt;", "</p><p>")
    body_html = body_html.replace("**", "<strong>")

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Executive Briefing - {dataset_name}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #222; max-width: 800px; margin: 40px auto; padding: 0 20px; }}
    h1 {{ color: #1e3a8a; border-bottom: 2px solid #e2e8f0; padding-bottom: 12px; }}
    h3 {{ color: #1e40af; margin-top: 24px; border-left: 4px solid #3b82f6; padding-left: 8px; }}
    strong {{ color: #0f172a; }}
    .badge {{ background: #eff6ff; color: #1d4ed8; padding: 4px 8px; border-radius: 4px; font-size: 13px; font-weight: bold; }}
    .footer {{ margin-top: 40px; font-size: 12px; color: #64748b; border-top: 1px solid #cbd5e1; padding-top: 12px; }}
  </style>
</head>
<body>
  <h1>📊 Executive Business Digest</h1>
  <p><span class="badge">Dataset: {dataset_name}</span> • Generated by AI Data Analytics Agent</p>
  <div>{body_html}</div>
  <div class="footer">Confidential • Generated automatically via AI Data Analytics & Entry Agent</div>
</body>
</html>"""
