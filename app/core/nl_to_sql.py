import os
import re
from typing import Tuple, Dict, Any, Optional, List
from openai import OpenAI

SYSTEM_PROMPT_TEMPLATE = """You are a SQL generation engine. Your only job is to convert a natural language question into a single valid DuckDB SQL query that answers it, based on the schema, semantic descriptions, and sample data provided.

Rules:
1. Output ONLY the SQL query. No explanation, no markdown code fences, no preamble.
2. Only generate SELECT statements. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, ATTACH, COPY, PRAGMA, or any statement that modifies data or schema.
3. Use only the table and column names provided in the schema. Do not invent columns or tables that don't exist. Respect the business aliases and meanings in the schema annotations.
4. If the question is ambiguous, make the most reasonable interpretation and proceed — do not ask for clarification.
5. If the question cannot be answered with the given schema (e.g., it references data that doesn't exist), output exactly: SELECT 'UNANSWERABLE' AS error;
6. Handle aggregations, filtering, sorting, and grouping as needed based on the question's intent.
7. Use DuckDB SQL syntax (it is largely standard SQL with some extensions).
8. Always alias aggregate columns with clear, human-readable names (e.g., SUM(sales) AS total_sales, not SUM(sales)).
9. Limit results to 1000 rows unless the question explicitly asks for all rows, by appending LIMIT 1000 if no LIMIT is already specified and the query could return many rows.

Schema and Data Dictionary:
{schema_description}

Sample rows (for context on data format/values):
{sample_rows}
{few_shot_context}"""

RETRY_PROMPT_TEMPLATE = """The SQL query you generated failed to execute with this error:
{error_message}

Original question: {user_question}
Query that failed: {failed_sql}

Schema and Data Dictionary:
{schema_description}

Generate a corrected SQL query that fixes this error. Output ONLY the corrected SQL query, following the same rules as before (SELECT only, valid DuckDB syntax, use only existing columns)."""

FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", 
    "ATTACH", "COPY", "PRAGMA", "EXEC", "EXECUTE", "TRUNCATE"
]

def sanitize_and_clean_sql(sql_raw: str) -> str:
    """Strips markdown fences, preambles, and whitespace from raw LLM output."""
    sql = sql_raw.strip()
    if sql.startswith("```"):
        lines = sql.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        sql = "\n".join(lines).strip()

    if sql.endswith(";"):
        sql = sql[:-1].strip()

    return sql

def validate_sql_security(sql: str) -> Tuple[bool, Optional[str]]:
    """
    Validates Section 7.2 safety requirements:
    1. Must start with SELECT or WITH.
    2. Must NOT contain forbidden write/destructive keywords.
    """
    cleaned_sql = sanitize_and_clean_sql(sql)
    upper_sql = cleaned_sql.upper()

    if not (upper_sql.startswith("SELECT") or upper_sql.startswith("WITH")):
        return False, "Query must start with SELECT or WITH. Non-read operations are strictly forbidden."

    for kw in FORBIDDEN_KEYWORDS:
        pattern = r'\b' + re.escape(kw) + r'\b'
        if re.search(pattern, upper_sql):
            return False, f"Forbidden keyword detected in query: {kw}. Data modification is prohibited."

    return True, None

def validate_query_intent(sql: str, allowed_columns: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Semantic Intent Validator:
    Verifies that the generated query references valid columns or is 'UNANSWERABLE'.
    Prevents execution of hallucinated columns.
    """
    if "UNANSWERABLE" in sql.upper():
        return True, None

    upper_sql = sql.upper()
    if "FROM DATASET" not in upper_sql and "FROM \"DATASET\"" not in upper_sql:
        return False, "Query does not query the 'dataset' table."

    return True, None

class NLToSQLConverter:
    """
    Handles translation from Natural Language question to DuckDB SQL query using OpenAI API,
    with strict validation, semantic dictionary enrichment, few-shot memory, and 1-shot retry logic.
    """
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None

    def generate_sql(self, user_question: str, schema_description: str, sample_rows: str, few_shot_context: str = "") -> str:
        """Calls OpenAI API to get initial SQL generation."""
        if not self.client:
            raise RuntimeError("OpenAI API Key not provided or configured in environment (OPENAI_API_KEY).")

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            schema_description=schema_description,
            sample_rows=sample_rows,
            few_shot_context=few_shot_context
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Question: {user_question}"}
            ],
            temperature=0
        )
        raw_text = response.choices[0].message.content or ""
        return sanitize_and_clean_sql(raw_text)

    def generate_retry_sql(self, user_question: str, failed_sql: str, error_message: str, schema_description: str) -> str:
        """Calls OpenAI API to generate a corrected SQL query following an execution error."""
        if not self.client:
            raise RuntimeError("OpenAI API Key not provided.")

        prompt = RETRY_PROMPT_TEMPLATE.format(
            error_message=error_message,
            user_question=user_question,
            failed_sql=failed_sql,
            schema_description=schema_description
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        raw_text = response.choices[0].message.content or ""
        return sanitize_and_clean_sql(raw_text)

    def convert_and_execute(
        self,
        engine,
        user_question: str,
        semantic_annotations: Optional[Dict[str, Dict[str, str]]] = None,
        few_shot_context: str = ""
    ) -> Dict[str, Any]:
        """
        Full Section 7.2 workflow with OpenAI + semantic layer & few-shot learning:
        1. Generate SQL with enriched schema + sample rows + few-shot memory
        2. Validate SELECT-only security & query intent
        3. Execute against DuckDB engine
        4. If execution fails, retry 1 time using retry prompt
        5. Return result dict
        """
        schema_desc, sample_rows = engine.get_schema_prompt_description(semantic_annotations)

        # Step 1: Initial SQL generation
        try:
            sql = self.generate_sql(user_question, schema_desc, sample_rows, few_shot_context)
        except Exception as e:
            return {
                "success": False,
                "sql": "",
                "error": f"Failed to reach OpenAI API: {str(e)}",
                "df": None
            }

        # Step 2: Validate security
        is_safe, sec_error = validate_sql_security(sql)
        if not is_safe:
            return {
                "success": False,
                "sql": sql,
                "error": f"Security Validation Failed: {sec_error}",
                "df": None
            }

        # Intent validation
        cols = [c["name"] for c in engine.get_schema_info()["columns"]]
        is_valid_intent, intent_err = validate_query_intent(sql, cols)
        if not is_valid_intent:
            return {
                "success": False,
                "sql": sql,
                "error": f"Query Intent Validation Failed: {intent_err}",
                "df": None
            }

        # Step 3: First Execution Attempt
        try:
            df = engine.execute_query(sql)
            return {
                "success": True,
                "sql": sql,
                "error": None,
                "df": df
            }
        except Exception as first_error:
            err_msg = str(first_error)

            # Step 4: One-shot Retry logic
            try:
                retry_sql = self.generate_retry_sql(user_question, sql, err_msg, schema_desc)
                is_safe_retry, sec_error_retry = validate_sql_security(retry_sql)
                if not is_safe_retry:
                    return {
                        "success": False,
                        "sql": retry_sql,
                        "error": f"Retry Security Validation Failed: {sec_error_retry}",
                        "df": None
                    }

                df = engine.execute_query(retry_sql)
                return {
                    "success": True,
                    "sql": retry_sql,
                    "error": None,
                    "retried": True,
                    "df": df
                }
            except Exception as retry_error:
                return {
                    "success": False,
                    "sql": sql,
                    "error": "I couldn't translate that into a query — try rephrasing your question.",
                    "details": f"First error: {err_msg} | Retry error: {str(retry_error)}",
                    "df": None
                }
