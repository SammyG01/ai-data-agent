import os
import json
import time
import shutil
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple

BASE_SESSIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".sessions"))

class SessionManager:
    """
    Manages persistent session state, file-backed storage, audit trails, and undo snapshots.
    Ensures zero data loss on browser refresh and allows instant rollback of applied fixes.
    Supports multi-tenant scoping by user_id.
    """
    def __init__(self, sessions_dir: str = BASE_SESSIONS_DIR):
        self.sessions_dir = sessions_dir
        os.makedirs(self.sessions_dir, exist_ok=True)

    def _get_session_dir(self, session_id: str) -> str:
        s_dir = os.path.join(self.sessions_dir, session_id)
        os.makedirs(s_dir, exist_ok=True)
        os.makedirs(os.path.join(s_dir, "snapshots"), exist_ok=True)
        return s_dir

    def _meta_path(self, session_id: str) -> str:
        return os.path.join(self._get_session_dir(session_id), "meta.json")

    def _data_path(self, session_id: str) -> str:
        return os.path.join(self._get_session_dir(session_id), "current_data.parquet")

    def create_or_update_session(
        self,
        session_id: str,
        df: pd.DataFrame,
        filename: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Initializes or updates session data and saves dataframe to parquet."""
        s_dir = self._get_session_dir(session_id)
        data_path = self._data_path(session_id)
        meta_path = self._meta_path(session_id)

        df.to_parquet(data_path, index=False)

        meta = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                meta = {}

        meta["session_id"] = session_id
        meta["filename"] = filename
        if user_id:
            meta["user_id"] = user_id
        meta["row_count"] = len(df)
        meta["col_count"] = len(df.columns)
        meta["last_updated"] = time.time()
        meta.setdefault("audit_log", [])
        meta.setdefault("query_history", [])
        meta.setdefault("data_dictionary", {})

        if metadata:
            meta.update(metadata)

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return meta

    def record_fix_snapshot(self, session_id: str, previous_df: pd.DataFrame, action_name: str, details: Dict[str, Any], user_id: Optional[str] = None) -> str:
        """
        Saves a snapshot of previous_df before applying a fix.
        Appends entry to audit log for rollback support.
        """
        s_dir = self._get_session_dir(session_id)
        meta = self.get_session_meta(session_id)
        audit_log = meta.get("audit_log", [])

        step = len(audit_log) + 1
        snapshot_filename = f"snapshot_step_{step}.parquet"
        snapshot_path = os.path.join(s_dir, "snapshots", snapshot_filename)

        previous_df.to_parquet(snapshot_path, index=False)

        record = {
            "step": step,
            "timestamp": time.time(),
            "action": action_name,
            "details": details,
            "user_id": user_id,
            "snapshot_file": snapshot_filename,
            "rows_before": len(previous_df),
            "cols_before": len(previous_df.columns)
        }
        audit_log.append(record)
        meta["audit_log"] = audit_log

        with open(self._meta_path(session_id), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return snapshot_filename

    def undo_last_fix(self, session_id: str) -> Tuple[Optional[pd.DataFrame], Optional[Dict[str, Any]]]:
        """
        Rolls back the dataset to the state immediately preceding the latest fix.
        Returns: (restored_dataframe, undone_record_details)
        """
        meta = self.get_session_meta(session_id)
        audit_log = meta.get("audit_log", [])

        if not audit_log:
            return None, None

        last_action = audit_log.pop()
        snapshot_filename = last_action["snapshot_file"]
        snapshot_path = os.path.join(self._get_session_dir(session_id), "snapshots", snapshot_filename)

        if not os.path.exists(snapshot_path):
            raise FileNotFoundError(f"Snapshot file {snapshot_filename} was not found on disk.")

        restored_df = pd.read_parquet(snapshot_path)
        restored_df.to_parquet(self._data_path(session_id), index=False)

        meta["audit_log"] = audit_log
        meta["row_count"] = len(restored_df)
        meta["col_count"] = len(restored_df.columns)
        meta["last_updated"] = time.time()
        meta.setdefault("undo_history", []).append({
            "undone_action": last_action,
            "undone_at": time.time()
        })

        with open(self._meta_path(session_id), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        try:
            os.remove(snapshot_path)
        except OSError:
            pass

        return restored_df, last_action

    def load_session_df(self, session_id: str) -> Optional[pd.DataFrame]:
        data_path = self._data_path(session_id)
        if os.path.exists(data_path):
            return pd.read_parquet(data_path)
        return None

    def get_session_meta(self, session_id: str) -> Dict[str, Any]:
        meta_path = self._meta_path(session_id)
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def update_session_meta(self, session_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        meta = self.get_session_meta(session_id)
        meta.update(updates)
        with open(self._meta_path(session_id), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        return meta

    def record_query(self, session_id: str, question: str, sql: str, row_count: int, success: bool, user_id: Optional[str] = None):
        meta = self.get_session_meta(session_id)
        history = meta.get("query_history", [])
        history.append({
            "timestamp": time.time(),
            "question": question,
            "sql": sql,
            "row_count": row_count,
            "success": success,
            "user_id": user_id
        })
        meta["query_history"] = history
        with open(self._meta_path(session_id), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    def list_sessions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists saved sessions. If user_id is provided, filters to sessions owned by that user or unowned."""
        sessions = []
        if not os.path.exists(self.sessions_dir):
            return sessions

        for s_id in os.listdir(self.sessions_dir):
            meta_path = os.path.join(self.sessions_dir, s_id, "meta.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        sess_owner = meta.get("user_id")

                        # Filter by user if specified
                        if user_id and sess_owner and sess_owner != user_id:
                            continue

                        sessions.append({
                            "session_id": s_id,
                            "user_id": sess_owner,
                            "filename": meta.get("filename", "Unknown"),
                            "row_count": meta.get("row_count", 0),
                            "last_updated": meta.get("last_updated", 0),
                            "audit_count": len(meta.get("audit_log", []))
                        })
                except Exception:
                    continue
        sessions.sort(key=lambda x: x.get("last_updated", 0), reverse=True)
        return sessions
