import pytest
import pandas as pd
from app.core.connectors import parse_google_sheets_url
from app.core.reporting import generate_dataset_profile, generate_executive_digest, generate_report_html
from app.core.voice import transcribe_audio

def test_google_sheets_url_parser():
    # Standard edit url
    url1 = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit?usp=sharing"
    exp1 = parse_google_sheets_url(url1)
    assert "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms" in exp1
    assert "export?format=csv&gid=0" in exp1

    # Specific tab/gid url
    url2 = "https://docs.google.com/spreadsheets/d/abc12345/edit#gid=987654"
    exp2 = parse_google_sheets_url(url2)
    assert "gid=987654" in exp2

    # Invalid url
    with pytest.raises(ValueError):
        parse_google_sheets_url("https://google.com/invalid-link")

def test_dataset_profile_and_reporting():
    df = pd.DataFrame({
        "sales": [100.0, 200.0, 300.0],
        "region": ["North", "South", "North"]
    })
    quality_report = {"total_issues": 1, "issues": [{"issue_type": "missing_values"}]}

    profile = generate_dataset_profile(df)
    assert profile["total_rows"] == 3
    assert profile["numeric_summary"]["sales"]["total"] == 600.0

    # Fallback report when no OpenAI key
    digest = generate_executive_digest(df, quality_report, dataset_name="Test Sales", api_key="")
    assert "Executive Summary" in digest
    assert "Test Sales" in digest

    # HTML generator
    html = generate_report_html(digest, "Test Sales")
    assert "<!DOCTYPE html>" in html
    assert "Test Sales" in html

def test_voice_transcription_input_validation():
    # Test error when no API key configured
    with pytest.raises(RuntimeError):
        transcribe_audio(b"fake_audio_bytes", api_key="")
