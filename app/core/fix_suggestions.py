import json
import os
from typing import Dict, Any, List, Optional
import anthropic
import pandas as pd
from app.core.fix_operations import SUPPORTED_OPERATIONS, execute_approved_fix

FIX_SUGGESTION_PROMPT_TEMPLATE = """You are proposing a fix for a data quality issue. You do not execute anything — you only describe a proposed fix in the exact structured format below, which a human will review and approve or reject.

Issue type: {issue_type}
Affected column(s): {column_names}
Details: {issue_details_json}
Sample of affected rows (before): {sample_affected_rows}

Choose exactly one fix from this fixed set of supported operations — do not invent new operation types:
- remove_duplicate_rows
- standardize_date_format
- standardize_text_format
- fill_missing_value
- custom_calculated_column
- regex_extract
- split_column
- replace_value_mapping
- remove_outliers

Respond ONLY in this JSON structure, nothing else:
{{
  "operation": "<one of the operation types above>",
  "target_column": "<column name, or null if not applicable>",
  "parameters": {{ "target_format": "YYYY-MM-DD", "strategy": "most_common", "casing": "title", "new_column": "clean_col", "delimiter": " ", "mapping": {{}} }},
  "explanation": "<one sentence, plain English, explaining what this fix does>",
  "preview_after": [ ... 2-3 example rows showing what they'd look like after the fix is applied ... ]
}}"""

class FixSuggester:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        else:
            self.client = None

    def generate_fix_proposals(self, df: pd.DataFrame, quality_report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generates structured fix proposals for each flagged data quality issue.
        Falls back to rule-based proposal generator if LLM is unavailable.
        """
        proposals = []
        issues = quality_report.get("issues", [])

        for idx, issue in enumerate(issues):
            issue_type = issue.get("issue_type")

            # Use LLM proposal generator if available
            proposal = None
            if self.client:
                try:
                    proposal = self._llm_propose_fix(df, issue)
                except Exception:
                    proposal = None

            # Fallback to rule-based heuristic proposal
            if not proposal:
                proposal = self._heuristic_propose_fix(df, issue)

            if proposal and proposal.get("operation") in SUPPORTED_OPERATIONS:
                proposal["id"] = f"fix_{idx}_{issue_type}"
                proposals.append(proposal)

        return proposals

    def _llm_propose_fix(self, df: pd.DataFrame, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        issue_type = issue.get("issue_type")
        affected_cols = ", ".join(issue.get("affected_columns", []))
        details_json = json.dumps(issue)
        sample_before = df.head(3).to_json(orient="records")

        prompt = FIX_SUGGESTION_PROMPT_TEMPLATE.format(
            issue_type=issue_type,
            column_names=affected_cols,
            issue_details_json=details_json,
            sample_affected_rows=sample_before
        )

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw_json = response.content[0].text.strip()
        if raw_json.startswith("```"):
            raw_json = raw_json.split("```")[1]
            if raw_json.startswith("json"):
                raw_json = raw_json[4:]
            raw_json = raw_json.strip()

        proposal = json.loads(raw_json)
        return proposal

    def _heuristic_propose_fix(self, df: pd.DataFrame, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministic rule-based proposal generator."""
        issue_type = issue.get("issue_type")
        affected_cols = issue.get("affected_columns", [])
        target_col = affected_cols[0] if affected_cols else None

        if issue_type == "duplicate_rows":
            preview_df = execute_approved_fix(df, "remove_duplicate_rows")
            return {
                "operation": "remove_duplicate_rows",
                "target_column": None,
                "parameters": {},
                "explanation": f"Remove all {issue.get('count', 0)} exact duplicate rows from the dataset.",
                "preview_after": preview_df.head(3).fillna("").to_dict(orient="records")
            }

        elif issue_type == "missing_values":
            preview_df = execute_approved_fix(df, "fill_missing_value", target_column=target_col, parameters={"strategy": "most_common"})
            return {
                "operation": "fill_missing_value",
                "target_column": target_col,
                "parameters": {"strategy": "most_common"},
                "explanation": f"Fill blank values in '{target_col}' using the most common value in that column.",
                "preview_after": preview_df.head(3).fillna("").to_dict(orient="records")
            }

        elif issue_type == "inconsistent_formatting":
            details = issue.get("details", [])
            detail_item = details[0] if details else {}
            fmt_type = detail_item.get("type", "")

            if fmt_type == "date_format":
                preview_df = execute_approved_fix(df, "standardize_date_format", target_column=target_col, parameters={"target_format": "YYYY-MM-DD"})
                return {
                    "operation": "standardize_date_format",
                    "target_column": target_col,
                    "parameters": {"target_format": "YYYY-MM-DD"},
                    "explanation": f"Standardize date formats in '{target_col}' to YYYY-MM-DD.",
                    "preview_after": preview_df.head(3).fillna("").to_dict(orient="records")
                }
            else:
                # If mixed casing detected, we can propose standardize_text_format or replace_value_mapping
                preview_df = execute_approved_fix(df, "standardize_text_format", target_column=target_col, parameters={"casing": "title", "strip_whitespace": True})
                return {
                    "operation": "standardize_text_format",
                    "target_column": target_col,
                    "parameters": {"casing": "title", "strip_whitespace": True},
                    "explanation": f"Trim whitespace and convert text casing to Title Case in '{target_col}'.",
                    "preview_after": preview_df.head(3).fillna("").to_dict(orient="records")
                }

        return {}
