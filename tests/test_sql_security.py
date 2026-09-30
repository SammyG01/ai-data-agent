import pytest
from app.core.nl_to_sql import validate_sql_security, sanitize_and_clean_sql

def test_sql_security_valid_queries():
    valid_queries = [
        "SELECT * FROM dataset LIMIT 10",
        "  SELECT region, COUNT(*) AS count FROM dataset GROUP BY region ORDER BY count DESC  ",
        "WITH regional_sales AS (SELECT region, SUM(revenue) as total FROM dataset GROUP BY region) SELECT * FROM regional_sales",
        "```sql\nSELECT product_category, AVG(revenue) AS avg_rev FROM dataset GROUP BY product_category\n```"
    ]
    for q in valid_queries:
        is_safe, err = validate_sql_security(q)
        assert is_safe is True, f"Query should be safe: {q} (Err: {err})"

def test_sql_security_forbidden_queries():
    forbidden_queries = [
        "DELETE FROM dataset WHERE revenue IS NULL",
        "DROP TABLE dataset",
        "UPDATE dataset SET revenue = 0",
        "INSERT INTO dataset VALUES (100, 'Test', 'Lagos', 500, '2024-01-01', 'Test User')",
        "CREATE TABLE hackers AS SELECT * FROM dataset",
        "ALTER TABLE dataset DROP COLUMN revenue",
        "SELECT * FROM dataset; DROP TABLE dataset;"
    ]
    for q in forbidden_queries:
        is_safe, err = validate_sql_security(q)
        assert is_safe is False, f"Query should be blocked: {q}"
