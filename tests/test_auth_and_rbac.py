import os
import shutil
import tempfile
import pytest
from app.auth.security import hash_password, verify_password, create_access_token, decode_access_token
from app.auth.models import UserManager, init_auth_db
from app.core.storage import SessionManager
import pandas as pd

def test_password_hashing_and_verification():
    raw_pass = "SecurePass123!"
    pwd_hash, salt = hash_password(raw_pass)

    assert pwd_hash != raw_pass
    assert verify_password(raw_pass, pwd_hash, salt) is True
    assert verify_password("WrongPass", pwd_hash, salt) is False

def test_jwt_token_lifecycle():
    token = create_access_token("user-123", "analyst@test.com", "Analyst")
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["email"] == "analyst@test.com"
    assert payload["role"] == "Analyst"

    # Malformed token test
    bad_payload = decode_access_token("malformed.token.here")
    assert bad_payload is None

def test_user_manager_and_roles():
    init_auth_db()

    # Authenticate seeded demo users
    admin = UserManager.authenticate_user("admin@demo.com", "admin123")
    assert admin is not None
    assert admin["role"] == "Admin"

    analyst = UserManager.authenticate_user("analyst@demo.com", "analyst123")
    assert analyst is not None
    assert analyst["role"] == "Analyst"

    dataentry = UserManager.authenticate_user("dataentry@demo.com", "entry123")
    assert dataentry is not None
    assert dataentry["role"] == "DataEntry"

    # Invalid password test
    invalid = UserManager.authenticate_user("admin@demo.com", "wrongpassword")
    assert invalid is None

def test_tenant_session_scoping():
    temp_dir = tempfile.mkdtemp()
    try:
        manager = SessionManager(sessions_dir=temp_dir)
        df = pd.DataFrame({"a": [1, 2]})

        manager.create_or_update_session("sess_user_1", df, "data1.csv", user_id="user_1")
        manager.create_or_update_session("sess_user_2", df, "data2.csv", user_id="user_2")

        # User 1 should only see their own sessions
        user1_sessions = manager.list_sessions(user_id="user_1")
        assert len(user1_sessions) == 1
        assert user1_sessions[0]["session_id"] == "sess_user_1"

        # Admin (user_id=None) sees all sessions
        all_sessions = manager.list_sessions(user_id=None)
        assert len(all_sessions) == 2
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
