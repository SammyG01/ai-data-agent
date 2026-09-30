import os
import shutil
import tempfile
import pandas as pd
import pytest
from app.core.storage import SessionManager

def test_session_lifecycle_and_undo():
    temp_dir = tempfile.mkdtemp()
    try:
        manager = SessionManager(sessions_dir=temp_dir)
        session_id = "test_sess_001"

        df_initial = pd.DataFrame({"id": [1, 2, 3], "val": ["A", "B", "C"]})
        manager.create_or_update_session(session_id, df_initial, "test.csv")

        # Verify initial save
        loaded_df = manager.load_session_df(session_id)
        assert len(loaded_df) == 3

        # Apply fix 1: modify df
        manager.record_fix_snapshot(session_id, df_initial, "test_action", {"detail": "step1"})
        df_modified = pd.DataFrame({"id": [1, 2], "val": ["A", "B"]})
        manager.create_or_update_session(session_id, df_modified, "test.csv")

        loaded_after_fix = manager.load_session_df(session_id)
        assert len(loaded_after_fix) == 2

        # Undo fix
        restored_df, undone = manager.undo_last_fix(session_id)
        assert undone["action"] == "test_action"
        assert len(restored_df) == 3

        # Current data on disk should also be restored
        disk_restored = manager.load_session_df(session_id)
        assert len(disk_restored) == 3

        # Second undo should return None (empty stack)
        empty_df, empty_undone = manager.undo_last_fix(session_id)
        assert empty_df is None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
