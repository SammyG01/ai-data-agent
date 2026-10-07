import streamlit as st
import pandas as pd
import json
import uuid
import os
import plotly.graph_objects as go
import plotly.io as pio

from app.core.engine import DuckDBEngine
from app.core.cleaning import detect_data_quality_issues
from app.core.nl_to_sql import NLToSQLConverter, validate_sql_security
from app.core.charting import infer_chart_type, generate_plotly_figure
from app.core.fix_operations import execute_approved_fix, SUPPORTED_OPERATIONS
from app.core.fix_suggestions import FixSuggester
from app.core.storage import SessionManager
from app.core.dictionary import DataDictionary, FewShotMemory
from app.core.safe_eval import evaluate_safe_expression
from app.auth.models import UserManager, init_auth_db
from app.auth.security import create_access_token
from app.core.connectors import load_google_sheet, load_sql_database
from app.core.reporting import generate_executive_digest, generate_report_html
from app.core.voice import transcribe_audio

st.set_page_config(
    page_title="DataPulse AI • Intelligent Analytics & Ingestion",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- MODERN DESIGN SYSTEM & GLASSMORPHISM CSS INJECTION ---
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

  html, body, [class*="css"] {
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  }
  
  code, pre, .stCodeBlock {
      font-family: 'JetBrains Mono', monospace !important;
  }

  /* App Background Styling */
  .stApp {
      background: radial-gradient(circle at 15% 15%, rgba(99, 102, 241, 0.08) 0%, transparent 40%),
                  radial-gradient(circle at 85% 85%, rgba(16, 185, 129, 0.05) 0%, transparent 40%),
                  #0B0F19;
  }

  /* Top Navigation Bar Component */
  .top-navbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 24px;
      margin-bottom: 24px;
      background: rgba(30, 41, 59, 0.4);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 16px;
      box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.2);
  }

  .brand-logo {
      display: flex;
      align-items: center;
      gap: 12px;
  }

  .brand-icon {
      background: linear-gradient(135deg, #6366F1 0%, #4F46E5 100%);
      color: white;
      width: 40px;
      height: 40px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      font-weight: 800;
      box-shadow: 0 0 15px rgba(99, 102, 241, 0.5);
  }

  .brand-title {
      font-size: 1.25rem;
      font-weight: 700;
      color: #F8FAFC;
      letter-spacing: -0.02em;
  }

  .brand-sub {
      font-size: 0.75rem;
      color: #94A3B8;
      font-weight: 500;
  }

  .nav-status {
      display: flex;
      align-items: center;
      gap: 16px;
  }

  .badge-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.02em;
  }

  .badge-admin { background: rgba(168, 85, 247, 0.15); color: #C084FC; border: 1px solid rgba(168, 85, 247, 0.3); }
  .badge-analyst { background: rgba(59, 130, 246, 0.15); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.3); }
  .badge-entry { background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.3); }
  .badge-online { background: rgba(34, 197, 94, 0.1); color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.2); }

  /* Glassmorphic Metric Cards */
  .metric-card {
      background: rgba(30, 41, 59, 0.45);
      border: 1px solid rgba(255, 255, 255, 0.07);
      backdrop-filter: blur(12px);
      border-radius: 16px;
      padding: 20px;
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  }

  .metric-card:hover {
      transform: translateY(-2px);
      border-color: rgba(99, 102, 241, 0.4);
      box-shadow: 0 10px 25px -5px rgba(99, 102, 241, 0.1);
  }

  .metric-title {
      font-size: 0.8rem;
      font-weight: 600;
      color: #94A3B8;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 8px;
  }

  .metric-val {
      font-size: 1.85rem;
      font-weight: 700;
      color: #F8FAFC;
      letter-spacing: -0.02em;
  }

  .metric-badge {
      display: inline-block;
      margin-top: 8px;
      font-size: 0.75rem;
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 6px;
  }

  /* Query Bubble Cards */
  .query-box {
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid rgba(99, 102, 241, 0.2);
      border-radius: 14px;
      padding: 18px;
      margin: 16px 0;
  }

  /* Buttons Styling */
  .stButton > button {
      border-radius: 10px !important;
      font-weight: 600 !important;
      letter-spacing: -0.01em !important;
      transition: all 0.2s ease !important;
  }

  .stButton > button:hover {
      box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3) !important;
  }

  /* Sidebar styling */
  section[data-testid="stSidebar"] {
      background-color: #0F172A !important;
      border-right: 1px solid rgba(255, 255, 255, 0.06);
  }

  /* Dataframe styling */
  .stDataFrame {
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.08);
  }

  /* Expanders */
  .streamlit-expanderHeader {
      background-color: rgba(30, 41, 59, 0.5) !important;
      border-radius: 10px !important;
      font-weight: 600 !important;
  }
</style>
""", unsafe_allow_html=True)

# Ensure authentication database is initialized
init_auth_db()
storage_manager = SessionManager()

# --- AUTHENTICATION STATE ---
if "user" not in st.session_state:
    st.session_state["user"] = None

def do_login(email: str, password: str) -> bool:
    user = UserManager.authenticate_user(email, password)
    if user:
        st.session_state["user"] = user
        st.session_state["token"] = create_access_token(user["id"], user["email"], user["role"])
        return True
    return False

def do_logout():
    st.session_state["user"] = None
    st.session_state["token"] = None
    st.rerun()

# --- LOGIN SCREEN IF NOT AUTHENTICATED ---
if st.session_state["user"] is None:
    st.markdown("""
    <div style="text-align: center; margin-top: 40px; margin-bottom: 30px;">
        <div style="display: inline-flex; align-items: center; gap: 12px; margin-bottom: 12px;">
            <div style="background: linear-gradient(135deg, #6366F1 0%, #4F46E5 100%); color: white; width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: 800; box-shadow: 0 0 25px rgba(99, 102, 241, 0.5);">⚡</div>
            <h1 style="font-size: 2.5rem; font-weight: 800; color: #F8FAFC; margin: 0; letter-spacing: -0.03em;">DataPulse AI</h1>
        </div>
        <p style="color: #94A3B8; font-size: 1.1rem; max-width: 600px; margin: 0 auto;">Enterprise Data Intelligence, Automated Cleaning & Natural Language Analytics for Modern Teams</p>
    </div>
    """, unsafe_allow_html=True)

    c_left, c_mid, c_right = st.columns([1, 2, 1])

    with c_mid:
        st.markdown("""
        <div style="background: rgba(30, 41, 59, 0.45); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 20px; padding: 28px; backdrop-filter: blur(20px); box-shadow: 0 20px 40px -15px rgba(0,0,0,0.5);">
        """, unsafe_allow_html=True)
        
        auth_mode = st.radio("Access Portal", ["Sign In", "Create Account"], horizontal=True)

        if auth_mode == "Sign In":
            with st.form("login_form"):
                email = st.text_input("Work Email", value="admin@demo.com")
                password = st.text_input("Password", type="password", value="admin123")
                submitted = st.form_submit_button("Sign In to Workspace", use_container_width=True)
                if submitted:
                    if do_login(email, password):
                        st.success(f"Welcome back, {st.session_state['user']['username']}!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")
        else:
            with st.form("register_form"):
                reg_name = st.text_input("Full Name", value="New User")
                reg_email = st.text_input("Work Email")
                reg_pass = st.text_input("Password", type="password")
                reg_role = st.selectbox("Role Permission", ["Analyst", "DataEntry"])
                reg_submit = st.form_submit_button("Create Workspace Account", use_container_width=True)
                if reg_submit:
                    try:
                        new_u = UserManager.create_user(reg_email, reg_name, reg_pass, reg_role)
                        do_login(reg_email, reg_pass)
                        st.success("Account created successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

        st.markdown("<hr style='border-color: rgba(255,255,255,0.06); margin: 24px 0;'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 0.8rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; margin-bottom: 12px;'>⚡ Instant Demo Sandbox Roles</div>", unsafe_allow_html=True)

        d1, d2, d3 = st.columns(3)
        with d1:
            if st.button("👑 Admin", use_container_width=True):
                do_login("admin@demo.com", "admin123")
                st.rerun()
        with d2:
            if st.button("📊 Analyst", use_container_width=True):
                do_login("analyst@demo.com", "analyst123")
                st.rerun()
        with d3:
            if st.button("✏️ Data Entry", use_container_width=True):
                do_login("dataentry@demo.com", "entry123")
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()

# --- AUTHENTICATED USER SESSION ---
current_user = st.session_state["user"]
user_role = current_user["role"]

# Session ID from query params or initialize new
params = st.query_params
active_session_id = params.get("session_id", None)
if not active_session_id:
    active_session_id = str(uuid.uuid4())
    st.query_params["session_id"] = active_session_id

# Initialize Session Engine & State
if "session_id" not in st.session_state or st.session_state["session_id"] != active_session_id:
    st.session_state["session_id"] = active_session_id
    st.session_state["engine"] = DuckDBEngine()
    st.session_state["dictionary"] = DataDictionary()
    st.session_state["few_shot"] = FewShotMemory()
    st.session_state["dataset_loaded"] = False
    st.session_state["quality_report"] = None
    st.session_state["proposals"] = []
    st.session_state["gsheet_url"] = None

    saved_df = storage_manager.load_session_df(active_session_id)
    if saved_df is not None:
        meta = storage_manager.get_session_meta(active_session_id)
        st.session_state["engine"].load_dataframe(saved_df)
        st.session_state["dictionary"] = DataDictionary(meta.get("data_dictionary"))
        for q in meta.get("query_history", []):
            if q.get("success"):
                st.session_state["few_shot"].add_verified_query(q["question"], q["sql"])
        st.session_state["quality_report"] = detect_data_quality_issues(saved_df)
        suggester = FixSuggester()
        st.session_state["proposals"] = suggester.generate_fix_proposals(saved_df, st.session_state["quality_report"])
        st.session_state["dataset_loaded"] = True
        st.session_state["gsheet_url"] = meta.get("gsheet_url")

# Role badge mapping
role_badge_class = {
    "Admin": "badge-admin",
    "Analyst": "badge-analyst",
    "DataEntry": "badge-entry"
}.get(user_role, "badge-admin")

# Top Modern Navbar
st.markdown(f"""
<div class="top-navbar">
    <div class="brand-logo">
        <div class="brand-icon">⚡</div>
        <div>
            <div class="brand-title">DataPulse AI</div>
            <div class="brand-sub">Session: {active_session_id[:8]}... • Cloud Active</div>
        </div>
    </div>
    <div class="nav-status">
        <span class="badge-pill badge-online">● DuckDB Engine Online</span>
        <span class="badge-pill {role_badge_class}">{user_role.upper()}</span>
        <span style="color: #F8FAFC; font-weight: 600; font-size: 0.9rem;">{current_user['username']}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar Design
with st.sidebar:
    st.markdown(f"""
    <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 14px; margin-bottom: 20px;">
        <div style="font-size: 0.95rem; font-weight: 700; color: #F8FAFC;">{current_user['username']}</div>
        <div style="font-size: 0.8rem; color: #94A3B8;">{current_user['email']}</div>
        <div style="margin-top: 8px;"><span class="badge-pill {role_badge_class}">{user_role}</span></div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Log Out", use_container_width=True):
        do_logout()

    st.markdown("---")
    st.subheader("Data Ingestion")

    data_source = st.radio("Source Type", ["File Upload", "Google Sheets", "Database URL"], horizontal=True)

    if data_source == "File Upload":
        uploaded_file = st.file_uploader("Upload CSV / XLSX", type=["csv", "xlsx", "xls"])
        if uploaded_file is not None:
            if not st.session_state["dataset_loaded"] or st.button("Process File", use_container_width=True):
                with st.spinner("Analyzing schema & quality..."):
                    ext = uploaded_file.name.split(".")[-1].lower()
                    if ext == "csv":
                        df = pd.read_csv(uploaded_file)
                    else:
                        df = pd.read_excel(uploaded_file)

                    st.session_state["engine"].load_dataframe(df)
                    st.session_state["dictionary"].initialize_from_df(df)
                    st.session_state["dataset_loaded"] = True
                    st.session_state["quality_report"] = detect_data_quality_issues(df)

                    storage_manager.create_or_update_session(
                        session_id=active_session_id,
                        df=df,
                        filename=uploaded_file.name,
                        user_id=current_user["id"],
                        metadata={"data_dictionary": st.session_state["dictionary"].get_all()}
                    )

                    suggester = FixSuggester()
                    st.session_state["proposals"] = suggester.generate_fix_proposals(df, st.session_state["quality_report"])
                    st.rerun()

    elif data_source == "Google Sheets":
        gsheet_input = st.text_input("Sheet Sharing URL", value=st.session_state.get("gsheet_url") or "", placeholder="https://docs.google.com/spreadsheets/d/...")
        c_load, c_sync = st.columns([1, 1])
        if c_load.button("Load Sheet", use_container_width=True):
            if gsheet_input:
                try:
                    with st.spinner("Connecting to Google Sheets..."):
                        df, name = load_google_sheet(gsheet_input)
                        st.session_state["engine"].load_dataframe(df)
                        st.session_state["dictionary"].initialize_from_df(df)
                        st.session_state["dataset_loaded"] = True
                        st.session_state["quality_report"] = detect_data_quality_issues(df)
                        st.session_state["gsheet_url"] = gsheet_input

                        storage_manager.create_or_update_session(
                            session_id=active_session_id,
                            df=df,
                            filename=name,
                            user_id=current_user["id"],
                            metadata={
                                "data_dictionary": st.session_state["dictionary"].get_all(),
                                "gsheet_url": gsheet_input
                            }
                        )
                        suggester = FixSuggester()
                        st.session_state["proposals"] = suggester.generate_fix_proposals(df, st.session_state["quality_report"])
                        st.success("Google Sheet loaded!")
                        st.rerun()
                except Exception as e:
                    st.error(str(e))

        if c_sync.button("🔄 Sync Live", use_container_width=True, disabled=not st.session_state.get("gsheet_url")):
            try:
                with st.spinner("Syncing latest live data..."):
                    df, name = load_google_sheet(st.session_state["gsheet_url"])
                    st.session_state["engine"].load_dataframe(df)
                    st.session_state["quality_report"] = detect_data_quality_issues(df)
                    storage_manager.create_or_update_session(
                        session_id=active_session_id,
                        df=df,
                        filename=name,
                        user_id=current_user["id"]
                    )
                    st.success("Live sync complete!")
                    st.rerun()
            except Exception as e:
                st.error(str(e))

    elif data_source == "Database URL":
        db_url = st.text_input("Connection String", placeholder="postgresql://...")
        db_target = st.text_input("Table / Query", placeholder="sales_data")
        if st.button("Connect Database", use_container_width=True):
            if db_url and db_target:
                try:
                    with st.spinner("Connecting..."):
                        df, name = load_sql_database(db_url, db_target)
                        st.session_state["engine"].load_dataframe(df)
                        st.session_state["dictionary"].initialize_from_df(df)
                        st.session_state["dataset_loaded"] = True
                        st.session_state["quality_report"] = detect_data_quality_issues(df)
                        storage_manager.create_or_update_session(session_id=active_session_id, df=df, filename=name, user_id=current_user["id"])
                        st.success("Database connected!")
                        st.rerun()
                except Exception as e:
                    st.error(str(e))

    # Saved Datasets Switcher
    saved_sessions = storage_manager.list_sessions(user_id=None if user_role == "Admin" else current_user["id"])
    if saved_sessions:
        st.markdown("---")
        st.subheader("Saved Workspaces")
        session_options = {f"{s['filename']} ({s['session_id'][:6]}...)": s['session_id'] for s in saved_sessions}
        selected_label = st.selectbox("Switch Workspace", list(session_options.keys()))
        if st.button("Switch", use_container_width=True):
            st.query_params["session_id"] = session_options[selected_label]
            st.rerun()

# Role-Based Mode Selector
if user_role == "Admin":
    allowed_modes = ["Data Analyst", "Data Entry", "User Administration"]
elif user_role == "Analyst":
    allowed_modes = ["Data Analyst"]
elif user_role == "DataEntry":
    allowed_modes = ["Data Entry"]
else:
    allowed_modes = ["Data Analyst"]

st.sidebar.markdown("---")
mode = st.sidebar.selectbox("Workspace Mode", allowed_modes, index=0)

if mode != "User Administration" and not st.session_state["dataset_loaded"]:
    st.info("👈 Connect a dataset (Upload CSV, connect Google Sheets or SQL) in the sidebar to begin analysis.")
    st.stop()

engine: DuckDBEngine = st.session_state["engine"]
dictionary: DataDictionary = st.session_state["dictionary"]
few_shot: FewShotMemory = st.session_state["few_shot"]
df_current = engine.df

# --- DATA ANALYST MODE ---
if mode == "Data Analyst":
    meta = storage_manager.get_session_meta(active_session_id)
    dataset_name = meta.get("filename", "Dataset")

    # High-impact Glassmorphic Metric Cards
    schema_info = engine.get_schema_info()
    qr = st.session_state["quality_report"]
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Active Rows</div>
            <div class="metric-val">{schema_info['row_count']:,}</div>
            <span class="metric-badge" style="background: rgba(99, 102, 241, 0.15); color: #818CF8;">In-Memory DuckDB</span>
        </div>
        """, unsafe_allow_html=True)
    with kpi2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Dimensions & Features</div>
            <div class="metric-val">{schema_info['col_count']}</div>
            <span class="metric-badge" style="background: rgba(59, 130, 246, 0.15); color: #60A5FA;">Indexed Columns</span>
        </div>
        """, unsafe_allow_html=True)
    with kpi3:
        issue_count = qr['total_issues'] if qr else 0
        issue_badge_bg = "rgba(244, 63, 94, 0.15)" if issue_count > 0 else "rgba(16, 185, 129, 0.15)"
        issue_badge_col = "#FB7185" if issue_count > 0 else "#34D399"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Data Quality Issues</div>
            <div class="metric-val">{issue_count}</div>
            <span class="metric-badge" style="background: {issue_badge_bg}; color: {issue_badge_col};">{"Attention Required" if issue_count > 0 else "Clean Baseline"}</span>
        </div>
        """, unsafe_allow_html=True)
    with kpi4:
        query_count = len(meta.get("query_history", []))
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">NL Queries Run</div>
            <div class="metric-val">{query_count}</div>
            <span class="metric-badge" style="background: rgba(168, 85, 247, 0.15); color: #C084FC;">AI Learning Enabled</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

    # Executive Briefing Expander
    with st.expander("📊 Executive AI Business Digest & Automated Reporting", expanded=False):
        st.markdown("Generate an automated Chief Data Officer briefing analyzing key business KPIs, trends, and risk assessment:")
        if st.button("Generate Executive Briefing", use_container_width=True):
            with st.spinner("Synthesizing executive briefing via OpenAI..."):
                try:
                    digest_md = generate_executive_digest(df_current, st.session_state["quality_report"], dataset_name=dataset_name)
                    st.session_state["executive_digest"] = digest_md
                except Exception as e:
                    st.error(f"Failed to generate briefing: {str(e)}")

        if "executive_digest" in st.session_state:
            st.markdown(st.session_state["executive_digest"])
            st.markdown("---")
            d_col1, d_col2 = st.columns([1, 1])
            with d_col1:
                st.download_button("📥 Export Briefing (.md)", data=st.session_state["executive_digest"], file_name=f"digest_{dataset_name}.md", mime="text/markdown", use_container_width=True)
            with d_col2:
                html_report = generate_report_html(st.session_state["executive_digest"], dataset_name)
                st.download_button("📥 Export Printable Report (.html)", data=html_report, file_name=f"report_{dataset_name}.html", mime="text/html", use_container_width=True)

    # Schema & Semantic Data Dictionary Expander
    with st.expander(f"📋 Semantic Data Dictionary ({schema_info['col_count']} Columns)", expanded=False):
        annotations = dictionary.get_all()
        for col in engine.df.columns:
            ann = annotations.get(col, {"alias": col, "unit": "N/A", "description": ""})
            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                new_alias = st.text_input(f"Alias `{col}`", value=ann.get("alias", col), key=f"alias_{col}")
            with c2:
                new_unit = st.text_input(f"Unit `{col}`", value=ann.get("unit", ""), key=f"unit_{col}")
            with c3:
                new_desc = st.text_input(f"Meaning `{col}`", value=ann.get("description", ""), key=f"desc_{col}")

            if new_alias != ann.get("alias") or new_unit != ann.get("unit") or new_desc != ann.get("description"):
                dictionary.update_column(col, alias=new_alias, unit=new_unit, description=new_desc)
                storage_manager.update_session_meta(active_session_id, {"data_dictionary": dictionary.get_all()})

    # Voice & Natural Language Query Box
    st.subheader("💬 Ask Your Dataset")
    
    # Modern Audio input
    audio_val = None
    if hasattr(st, "audio_input"):
        audio_val = st.audio_input("🎙️ Voice Input (Microphone)")
    else:
        audio_val = st.file_uploader("🎙️ Voice Input (Upload audio)", type=["wav", "mp3", "m4a"])

    transcribed_text = None
    if audio_val:
        with st.spinner("Transcribing voice via OpenAI Whisper..."):
            try:
                audio_bytes = audio_val.read()
                transcribed_text = transcribe_audio(audio_bytes, filename="audio.wav")
                st.info(f"🎙️ Transcribed Voice: *\"{transcribed_text}\"*")
            except Exception as e:
                st.error(f"Voice transcription failed: {str(e)}")

    q_col1, q_col2 = st.columns([4, 1])
    with q_col1:
        user_question = st.text_input(
            "Natural Language Query",
            value=transcribed_text if transcribed_text else "",
            placeholder="e.g. What is total sales grouped by region? Top 5 customers by revenue?",
            key="nl_input",
            label_visibility="collapsed"
        )
    with q_col2:
        run_btn = st.button("🚀 Analyze", use_container_width=True)

    if (run_btn or (transcribed_text and st.button("Execute Voice Query"))) and user_question:
        with st.spinner("Generating DuckDB SQL via OpenAI..."):
            converter = NLToSQLConverter()
            few_shot_ctx = few_shot.format_prompt_examples()
            result = converter.convert_and_execute(
                engine=engine,
                user_question=user_question,
                semantic_annotations=dictionary.get_all(),
                few_shot_context=few_shot_ctx
            )

            if not result["success"]:
                st.error(f"❌ Query Error: {result.get('error')}")
                if result.get("details"):
                    st.caption(result["details"])
            else:
                st.session_state["last_result"] = result
                storage_manager.record_query(active_session_id, user_question, result["sql"], len(result["df"]), True, user_id=current_user["id"])
                few_shot.add_verified_query(user_question, result["sql"])

    if "last_result" in st.session_state:
        res = st.session_state["last_result"]
        df_res: pd.DataFrame = res["df"]

        st.markdown(f"""
        <div class="query-box">
            <div style="font-weight: 700; color: #F8FAFC; margin-bottom: 8px;">🔍 Query: {res['question']}</div>
            <div style="font-size: 0.8rem; color: #94A3B8;">Executed SQL (DuckDB):</div>
        </div>
        """, unsafe_allow_html=True)
        st.code(res["sql"], language="sql")

        tab_table, tab_chart = st.tabs(["📊 Table Preview", "📈 Intelligent Chart"])
        with tab_table:
            st.dataframe(df_res, use_container_width=True)
            csv_data = df_res.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export CSV", data=csv_data, file_name="query_results.csv", mime="text/csv")

        with tab_chart:
            auto_chart, def_x, def_y = infer_chart_type(df_res)
            c1, c2 = st.columns([1, 3])
            with c1:
                chart_override = st.selectbox("Chart Type", ["auto", "bar", "line", "pie", "scatter", "metric", "table"], index=0)
                selected_chart = auto_chart if chart_override == "auto" else chart_override
            with c2:
                if selected_chart != "table":
                    fig = generate_plotly_figure(df_res, selected_chart, def_x, def_y)
                    if fig:
                        fig.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#F8FAFC", family="Plus Jakarta Sans"),
                            colorway=["#6366F1", "#10B981", "#F59E0B", "#EC4899", "#06B6D4"]
                        )
                        st.plotly_chart(fig, use_container_width=True)

# --- DATA ENTRY MODE ---
elif mode == "Data Entry":
    st.header("✏️ Data Entry & Quality Review")

    qr = st.session_state["quality_report"]
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""<div class="metric-card"><div class="metric-title">Total Records</div><div class="metric-val">{qr['total_rows']:,}</div></div>""", unsafe_allow_html=True)
    with m2:
        st.markdown(f"""<div class="metric-card"><div class="metric-title">Hygiene Issues</div><div class="metric-val">{qr['total_issues']}</div></div>""", unsafe_allow_html=True)
    with m3:
        dup_issue = next((i for i in qr["issues"] if i["issue_type"] == "duplicate_rows"), None)
        dup_cnt = dup_issue["count"] if dup_issue else 0
        st.markdown(f"""<div class="metric-card"><div class="metric-title">Duplicate Rows</div><div class="metric-val">{dup_cnt}</div></div>""", unsafe_allow_html=True)
    with m4:
        meta = storage_manager.get_session_meta(active_session_id)
        audit_log = meta.get("audit_log", [])
        st.markdown(f"""<div class="metric-card"><div class="metric-title">Actions History</div><div class="metric-val">{len(audit_log)}</div></div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
    
    if st.button("⏪ Undo Last Fix (Rollback Snapshot)", disabled=len(audit_log) == 0, use_container_width=True):
        with st.spinner("Rolling back state..."):
            restored_df, undone = storage_manager.undo_last_fix(active_session_id)
            if restored_df is not None:
                engine.load_dataframe(restored_df)
                st.session_state["quality_report"] = detect_data_quality_issues(restored_df)
                suggester = FixSuggester()
                st.session_state["proposals"] = suggester.generate_fix_proposals(restored_df, st.session_state["quality_report"])
                st.success(f"Rolled back: {undone.get('action')}")
                st.rerun()

    st.markdown("---")
    st.subheader("💡 Automated Fix Proposals")
    proposals = st.session_state["proposals"]

    if not proposals:
        st.success("✅ Dataset is completely clean of flagged hygiene issues.")
    else:
        for idx, prop in enumerate(proposals):
            st.markdown(f"""
            <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 18px; margin-bottom: 16px;">
                <div style="font-size: 1.05rem; font-weight: 700; color: #F8FAFC;">Fix #{idx + 1}: {prop['explanation']}</div>
                <div style="font-size: 0.8rem; color: #94A3B8; margin-bottom: 12px;">Operation: <code style="color: #818CF8;">{prop['operation']}</code> • Target: <code>{prop.get('target_column', 'N/A')}</code></div>
            </div>
            """, unsafe_allow_html=True)

            col_b, col_a = st.columns(2)
            with col_b:
                st.caption("Current Records")
                st.dataframe(df_current.head(3), use_container_width=True)
            with col_a:
                st.caption("Preview After Fix")
                if "preview_after" in prop:
                    st.dataframe(pd.DataFrame(prop["preview_after"]), use_container_width=True)

            if st.button(f"Approve & Apply Fix #{idx + 1}", key=f"app_{idx}", use_container_width=True):
                with st.spinner("Applying fix..."):
                    storage_manager.record_fix_snapshot(
                        session_id=active_session_id,
                        previous_df=df_current,
                        action_name=prop["operation"],
                        details={"target_column": prop.get("target_column"), "parameters": prop.get("parameters", {})},
                        user_id=current_user["id"]
                    )
                    updated_df = execute_approved_fix(df_current, prop["operation"], target_column=prop.get("target_column"), parameters=prop.get("parameters", {}))
                    engine.load_dataframe(updated_df)
                    storage_manager.create_or_update_session(active_session_id, updated_df, meta.get("filename", "dataset.csv"), user_id=current_user["id"])
                    st.session_state["quality_report"] = detect_data_quality_issues(updated_df)
                    suggester = FixSuggester()
                    st.session_state["proposals"] = suggester.generate_fix_proposals(updated_df, st.session_state["quality_report"])
                    st.success("Fix applied!")
                    st.rerun()

    # Advanced Calculations & Transformations
    with st.expander("⚡ Advanced Safe Transformations (AST Sandbox)", expanded=False):
        adv_tab1, adv_tab2, adv_tab3 = st.tabs(["Calculated Column", "Split Column", "Regex Extract"])
        with adv_tab1:
            f_col1, f_col2 = st.columns([1, 2])
            new_col_name = f_col1.text_input("New Column Name", value="tax_amount")
            formula_expr = f_col2.text_input("Formula Expression", value="revenue * 0.075")
            if st.button("Apply Formula", use_container_width=True):
                try:
                    storage_manager.record_fix_snapshot(active_session_id, df_current, "custom_calculated_column", {"new_column": new_col_name, "expression": formula_expr}, user_id=current_user["id"])
                    updated_df = execute_approved_fix(df_current, "custom_calculated_column", parameters={"new_column": new_col_name, "expression": formula_expr})
                    engine.load_dataframe(updated_df)
                    storage_manager.create_or_update_session(active_session_id, updated_df, meta.get("filename", "dataset.csv"), user_id=current_user["id"])
                    st.success("Column created!")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        with adv_tab2:
            s_col1, s_col2 = st.columns([1, 1])
            split_target = s_col1.selectbox("Column to Split", df_current.columns)
            delimiter = s_col2.text_input("Delimiter", value=" ")
            if st.button("Apply Split", use_container_width=True):
                try:
                    storage_manager.record_fix_snapshot(active_session_id, df_current, "split_column", {"target_column": split_target, "delimiter": delimiter}, user_id=current_user["id"])
                    updated_df = execute_approved_fix(df_current, "split_column", target_column=split_target, parameters={"delimiter": delimiter})
                    engine.load_dataframe(updated_df)
                    storage_manager.create_or_update_session(active_session_id, updated_df, meta.get("filename", "dataset.csv"), user_id=current_user["id"])
                    st.success("Column split!")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        with adv_tab3:
            r_col1, r_col2 = st.columns([1, 2])
            rx_target = r_col1.selectbox("Target Column", df_current.columns, key="rx_tgt")
            rx_pattern = r_col2.text_input("Regex Pattern", value=r"\d+", key="rx_pat")
            if st.button("Apply Regex Extract", use_container_width=True):
                try:
                    storage_manager.record_fix_snapshot(active_session_id, df_current, "regex_extract", {"target_column": rx_target, "pattern": rx_pattern}, user_id=current_user["id"])
                    updated_df = execute_approved_fix(df_current, "regex_extract", target_column=rx_target, parameters={"pattern": rx_pattern})
                    engine.load_dataframe(updated_df)
                    storage_manager.create_or_update_session(active_session_id, updated_df, meta.get("filename", "dataset.csv"), user_id=current_user["id"])
                    st.success("Regex extracted!")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    st.subheader("➕ Manual Record Entry")
    with st.form("add_row_form"):
        new_row = {}
        form_cols = st.columns(min(len(df_current.columns), 4))
        for i, col in enumerate(df_current.columns):
            with form_cols[i % 4]:
                new_row[col] = st.text_input(f"{col}")
        if st.form_submit_button("Add Record", use_container_width=True):
            storage_manager.record_fix_snapshot(active_session_id, df_current, "manual_add_record", {"row": new_row}, user_id=current_user["id"])
            new_df = pd.concat([df_current, pd.DataFrame([new_row])], ignore_index=True)
            engine.load_dataframe(new_df)
            storage_manager.create_or_update_session(active_session_id, new_df, meta.get("filename", "dataset.csv"), user_id=current_user["id"])
            st.success("Record appended!")
            st.rerun()

    st.markdown("---")
    cleaned_csv = engine.df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Export Cleaned Dataset (CSV)", data=cleaned_csv, file_name="cleaned_dataset.csv", mime="text/csv", use_container_width=True)

# --- ADMIN PANEL ---
elif mode == "User Administration" and user_role == "Admin":
    st.header("👥 User Administration & RBAC Management")
    users = UserManager.list_users()
    users_df = pd.DataFrame(users)
    users_df["created_at"] = pd.to_datetime(users_df["created_at"], unit="s")
    st.dataframe(users_df[["username", "email", "role", "created_at"]], use_container_width=True)

    st.subheader("Change User Role")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        user_select = st.selectbox("Select User", [f"{u['username']} ({u['email']})" for u in users])
    with c2:
        new_role = st.selectbox("New Role", ["Admin", "Analyst", "DataEntry"])
    with c3:
        st.write("")
        if st.button("Update Role", use_container_width=True):
            selected_email = user_select.split("(")[-1].rstrip(")")
            target_user = next((u for u in users if u["email"] == selected_email), None)
            if target_user:
                UserManager.update_user_role(target_user["id"], new_role)
                st.success(f"Updated {target_user['username']} to {new_role}")
                st.rerun()
