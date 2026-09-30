import sqlite3
import os
import uuid
import time
from typing import Dict, Any, Optional, List
from app.auth.security import hash_password, verify_password

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".sessions", "auth.db"))

def get_db_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_auth_db():
    """Initializes authentication database schema and seeds initial demo users."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        username TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at REAL NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        row_count INTEGER DEFAULT 0,
        last_active REAL NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)

    conn.commit()

    # Seed default demo accounts if table is empty
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]

    if count == 0:
        demo_users = [
            {"email": "admin@demo.com", "username": "Admin User", "password": "admin123", "role": "Admin"},
            {"email": "analyst@demo.com", "username": "Data Analyst", "password": "analyst123", "role": "Analyst"},
            {"email": "dataentry@demo.com", "username": "Data Entry Staff", "password": "entry123", "role": "DataEntry"}
        ]
        for u in demo_users:
            pwd_hash, salt = hash_password(u["password"])
            user_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO users (id, email, username, password_hash, salt, role, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, u["email"], u["username"], pwd_hash, salt, u["role"], time.time())
            )
        conn.commit()

    conn.close()

class UserManager:
    @staticmethod
    def create_user(email: str, username: str, password: str, role: str = "Analyst") -> Dict[str, Any]:
        """Creates a new user account with hashed password."""
        valid_roles = ["Admin", "Analyst", "DataEntry"]
        if role not in valid_roles:
            raise ValueError(f"Invalid role '{role}'. Must be one of {valid_roles}")

        email = email.strip().lower()
        pwd_hash, salt = hash_password(password)
        user_id = str(uuid.uuid4())
        created_at = time.time()

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (id, email, username, password_hash, salt, role, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, email, username.strip(), pwd_hash, salt, role, created_at)
            )
            conn.commit()
            return {
                "id": user_id,
                "email": email,
                "username": username,
                "role": role,
                "created_at": created_at
            }
        except sqlite3.IntegrityError:
            raise ValueError(f"User with email '{email}' already exists.")
        finally:
            conn.close()

    @staticmethod
    def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
        """Verifies credentials and returns user dict if valid."""
        email = email.strip().lower()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        if verify_password(password, row["password_hash"], row["salt"]):
            return {
                "id": row["id"],
                "email": row["email"],
                "username": row["username"],
                "role": row["role"],
                "created_at": row["created_at"]
            }
        return None

    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves user by ID."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, username, role, created_at FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    @staticmethod
    def list_users() -> List[Dict[str, Any]]:
        """Lists all registered users (for Admin dashboard)."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, username, role, created_at FROM users ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def update_user_role(user_id: str, new_role: str):
        """Updates user role (Admin action)."""
        valid_roles = ["Admin", "Analyst", "DataEntry"]
        if new_role not in valid_roles:
            raise ValueError(f"Invalid role: {new_role}")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
        conn.commit()
        conn.close()
