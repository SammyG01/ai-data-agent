import pandas as pd
import pytest
from app.core.dictionary import DataDictionary, FewShotMemory
from app.core.engine import DuckDBEngine

def test_data_dictionary_and_few_shot():
    df = pd.DataFrame({
        "order_id": [1, 2],
        "rev": [5000.0, 10000.0],
        "reg": ["Lagos", "Abuja"]
    })

    dictionary = DataDictionary()
    dictionary.initialize_from_df(df)

    annotations = dictionary.get_all()
    assert annotations["rev"]["alias"] == "Revenue"
    assert "Naira" in annotations["rev"]["unit"]

    # Manual update
    dictionary.update_column("reg", alias="Sales Territory", description="Nigerian geopolitical region")
    assert dictionary.get_all()["reg"]["alias"] == "Sales Territory"

    # Engine prompt formatting with annotations
    engine = DuckDBEngine()
    engine.load_dataframe(df)
    schema_desc, sample_rows = engine.get_schema_prompt_description(dictionary.get_all())

    assert "Sales Territory" in schema_desc
    assert "Revenue" in schema_desc

    # Few-shot memory test
    memory = FewShotMemory()
    memory.add_verified_query("What is total revenue?", "SELECT SUM(rev) AS total_revenue FROM dataset")
    formatted = memory.format_prompt_examples()
    assert "What is total revenue?" in formatted
    assert "SELECT SUM(rev)" in formatted
