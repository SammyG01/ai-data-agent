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

st.set_page_config(
    page_title="AI Data Analytics & Entry Agent (Multi-User SaaS)",
    page_icon="📊",
    layout="wide"
)

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
    st.title("📊 AI Data Analytics & Entry Agent")
    st.caption("Secure Multi-Tenant SaaS Platform for SMEs • Please sign in to continue")

    login_col, demo_col = st.columns([1, 1], gap="large")

    with login_col:
        auth_mode = st.radio("Choose action", ["Sign In", "Create Account"], horizontal=True)

        if auth_mode == "Sign In":
            with st.form("login_form"):
                email = st.text_input("Email Address", value="admin@demo.com")
                password = st.text_input("Password", type="password", value="admin123")
                submitted = st.form_submit_button("Sign In", use_container_width=True)
                if submitted:
                    if do_login(email, password):
                        st.success(f"Welcome back, {st.session_state['user']['username']}!")
                        st.rerun()
                    else:
                        st.error("Invalid email or password.")
        else:
            with st.form("register_form"):
                reg_name = st.text_input("Full Name", value="New User")
                reg_email = st.text_input("Email Address")
                reg_pass = st.text_input("Password", type="password")
                reg_role = st.selectbox("Role", ["Analyst", "DataEntry"])
                reg_submit = st.form_submit_button("Create Account", use_container_width=True)
                if reg_submit:
                    try:
                        new_u = UserManager.create_user(reg_email, reg_name, reg_pass, reg_role)
                        do_login(reg_email, reg_pass)
                        st.success("Account created successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    with demo_col:
        st.info("### ⚡ Quick Demo Logins")
        st.markdown("Test each role's permissions with a single click:")

        if st.button("🔑 Login as Admin (Full Control)", use_container_width=True):
            do_login("admin@demo.com", "admin123")
            st.rerun()

        if st.button("📈 Login as Data Analyst (Query & Viz Only)", use_container_width=True):
            do_login("analyst@demo.com", "analyst123")
            st.rerun()

        if st.button("✏️ Login as Data Entry (Cleaning & Fixes Only)", use_container_width=True):
            do_login("dataentry@demo.com", "entry123")
            st.rerun()

        st.markdown("""
        **Role Capabilities:**
        - **Admin**: Full access to all modes + User Administration panel.
        - **Data Analyst**: Natural language querying, charts, semantic data dictionary.
        - **Data Entry**: Data quality review, 1-click approvals, manual record entry, and rollback.
        """)

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

    # Attempt to restore persisted session from disk if exists
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

# Header & Sidebar
st.title("📊 AI Data Analytics & Entry Agent")
st.caption(f"Session: `{active_session_id[:8]}...` • Tenant User: **{current_user['username']}** (`{user_role}`)")

with st.sidebar:
    st.subheader(f"👤 {current_user['username']}")
    st.caption(f"Role: `{user_role}` • {current_user['email']}")
    if st.button("Log Out", use_container_width=True):
        do_logout()

    st.markdown("---")
    st.header("Dataset Control")
    uploaded_file = st.file_uploader("Upload CSV or XLSX Dataset", type=["csv", "xlsx", "xls"])

    if uploaded_file is not None:
        if not st.session_state["dataset_loaded"] or st.button("Re-process Uploaded File"):
            with st.spinner("Loading file & analyzing data quality..."):
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

    # User-Scoped Session Switcher
    saved_sessions = storage_manager.list_sessions(user_id=None if user_role == "Admin" else current_user["id"])
    if saved_sessions:
        st.markdown("---")
        st.subheader("Saved Datasets")
        session_options = {f"{s['filename']} ({s['session_id'][:8]}...)": s['session_id'] for s in saved_sessions}
        selected_label = st.selectbox("Switch Dataset", list(session_options.keys()))
        if st.button("Switch"):
            st.query_params["session_id"] = session_options[selected_label]
            st.rerun()

# Role-Based Mode Selector
st.sidebar.markdown("---")
if user_role == "Admin":
    allowed_modes = ["Data Analyst", "Data Entry", "User Administration"]
elif user_role == "Analyst":
    allowed_modes = ["Data Analyst"]
elif user_role == "DataEntry":
    allowed_modes = ["Data Entry"]
else:
    allowed_modes = ["Data Analyst"]

mode = st.sidebar.selectbox("Active Mode", allowed_modes, index=0)

if mode != "User Administration" and not st.session_state["dataset_loaded"]:
    st.info("👈 Please upload a dataset (CSV or Excel) in the sidebar or switch to a saved dataset.")
    st.stop()

engine: DuckDBEngine = st.session_state["engine"]
dictionary: DataDictionary = st.session_state["dictionary"]
few_shot: FewShotMemory = st.session_state["few_shot"]
df_current = engine.df

# --- DATA ANALYST MODE ---
if mode == "Data Analyst":
    st.header("🔍 Data Analyst Panel")

    # Schema & Semantic Data Dictionary Expander
    schema_info = engine.get_schema_info()
    with st.expander(f"📋 Semantic Data Dictionary ({schema_info['row_count']} rows, {schema_info['col_count']} columns)", expanded=False):
        st.markdown("Define business terms and meanings for each column to enhance natural-language understanding:")
        annotations = dictionary.get_all()

        for col in engine.df.columns:
            ann = annotations.get(col, {"alias": col, "unit": "N/A", "description": ""})
            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                new_alias = st.text_input(f"Alias for `{col}`", value=ann.get("alias", col), key=f"alias_{col}")
            with c2:
                new_unit = st.text_input(f"Unit for `{col}`", value=ann.get("unit", ""), key=f"unit_{col}")
            with c3:
                new_desc = st.text_input(f"Meaning of `{col}`", value=ann.get("description", ""), key=f"desc_{col}")

            if new_alias != ann.get("alias") or new_unit != ann.get("unit") or new_desc != ann.get("description"):
                dictionary.update_column(col, alias=new_alias, unit=new_unit, description=new_desc)
                storage_manager.update_session_meta(active_session_id, {"data_dictionary": dictionary.get_all()})

    user_question = st.text_input(
        "Ask a question in plain English:",
        placeholder="e.g. What is total sales by region? What are the top 5 products by revenue?",
        key="nl_input"
    )

    if st.button("Run Query") and user_question:
        with st.spinner("Analyzing intent and generating DuckDB SQL..."):
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

        st.subheader(f"Query Result: {res['question']}")
        st.code(res["sql"], language="sql")
        if res.get("retried"):
            st.caption("ℹ️ Query was automatically refined using DuckDB feedback loop.")

        st.dataframe(df_res, use_container_width=True)

        auto_chart, def_x, def_y = infer_chart_type(df_res)
        st.markdown("---")
        c1, c2 = st.columns([1, 3])
        with c1:
            chart_override = st.selectbox(
                "Chart Type Override", 
                ["auto", "bar", "line", "pie", "scatter", "metric", "table"], 
                index=0
            )
            selected_chart = auto_chart if chart_override == "auto" else chart_override

        with c2:
            if selected_chart != "table":
                fig = generate_plotly_figure(df_res, selected_chart, def_x, def_y)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("Could not auto-render chart for selected layout.")

        st.markdown("---")
        csv_data = df_res.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Export Query Results (CSV)", data=csv_data, file_name="query_results.csv", mime="text/csv")

    meta = storage_manager.get_session_meta(active_session_id)
    history = meta.get("query_history", [])
    if history:
        with st.expander(f"⏱️ Session Query History ({len(history)} queries)", expanded=False):
            hist_df = pd.DataFrame(history)
            st.dataframe(hist_df[["question", "sql", "row_count", "success"]], use_container_width=True)

# --- DATA ENTRY MODE ---
elif mode == "Data Entry":
    st.header("✏️ Data Entry & Quality Review Panel")

    qr = st.session_state["quality_report"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Rows", qr["total_rows"])
    m2.metric("Flagged Quality Issues", qr["total_issues"])
    dup_issue = next((i for i in qr["issues"] if i["issue_type"] == "duplicate_rows"), None)
    m3.metric("Duplicate Rows", dup_issue["count"] if dup_issue else 0)

    meta = storage_manager.get_session_meta(active_session_id)
    audit_log = meta.get("audit_log", [])
    with m4:
        st.write("")
        if st.button("⏪ Undo Last Fix", disabled=len(audit_log) == 0):
            with st.spinner("Rolling back to previous snapshot..."):
                restored_df, undone = storage_manager.undo_last_fix(active_session_id)
                if restored_df is not None:
                    engine.load_dataframe(restored_df)
                    st.session_state["quality_report"] = detect_data_quality_issues(restored_df)
                    suggester = FixSuggester()
                    st.session_state["proposals"] = suggester.generate_fix_proposals(restored_df, st.session_state["quality_report"])
                    st.success(f"Rolled back action: {undone.get('action')}")
                    st.rerun()

    st.markdown("---")

    st.subheader("💡 Proposed Fixes (Human Review Required)")
    proposals = st.session_state["proposals"]

    if not proposals:
        st.success("✅ No data quality fixes pending.")
    else:
        for idx, prop in enumerate(proposals):
            with st.container():
                st.markdown(f"#### Fix #{idx + 1}: {prop['explanation']}")
                st.caption(f"**Operation**: `{prop['operation']}` | **Target Column**: `{prop.get('target_column', 'N/A')}`")

                col_b, col_a = st.columns(2)
                with col_b:
                    st.caption("Preview Before Fix")
                    st.dataframe(df_current.head(3), use_container_width=True)
                with col_a:
                    st.caption("Preview After Fix")
                    if "preview_after" in prop:
                        st.dataframe(pd.DataFrame(prop["preview_after"]), use_container_width=True)

                if st.button(f"Approve Fix #{idx + 1}", key=f"app_{idx}"):
                    with st.spinner("Applying approved fix and creating undo snapshot..."):
                        storage_manager.record_fix_snapshot(
                            session_id=active_session_id,
                            previous_df=df_current,
                            action_name=prop["operation"],
                            details={"target_column": prop.get("target_column"), "parameters": prop.get("parameters", {})},
                            user_id=current_user["id"]
                        )
                        updated_df = execute_approved_fix(
                            df_current, 
                            prop["operation"], 
                            target_column=prop.get("target_column"), 
                            parameters=prop.get("parameters", {})
                        )
                        engine.load_dataframe(updated_df)
                        storage_manager.create_or_update_session(active_session_id, updated_df, meta.get("filename", "dataset.csv"), user_id=current_user["id"])
                        st.session_state["quality_report"] = detect_data_quality_issues(updated_df)
                        suggester = FixSuggester()
                        st.session_state["proposals"] = suggester.generate_fix_proposals(updated_df, st.session_state["quality_report"])
                        st.success("Fix applied successfully!")
                        st.rerun()

                st.markdown("---")

    with st.expander("⚡ Advanced Transformations & Custom Formulas (Safe Sandbox)", expanded=False):
        adv_tab1, adv_tab2, adv_tab3 = st.tabs(["Calculated Column", "Split Column", "Regex Extract"])

        with adv_tab1:
            st.caption("Calculate a new column using safe math expressions (e.g. `revenue * 0.15`)")
            f_col1, f_col2 = st.columns([1, 2])
            new_col_name = f_col1.text_input("New Column Name", value="tax_amount")
            formula_expr = f_col2.text_input("Formula Expression", value="revenue * 0.075")
            if st.button("Apply Formula"):
                try:
                    storage_manager.record_fix_snapshot(
                        active_session_id, df_current, "custom_calculated_column",
                        {"new_column": new_col_name, "expression": formula_expr},
                        user_id=current_user["id"]
                    )
                    updated_df = execute_approved_fix(
                        df_current, "custom_calculated_column",
                        parameters={"new_column": new_col_name, "expression": formula_expr}
                    )
                    engine.load_dataframe(updated_df)
                    storage_manager.create_or_update_session(active_session_id, updated_df, meta.get("filename", "dataset.csv"), user_id=current_user["id"])
                    st.success(f"Column '{new_col_name}' calculated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Calculation failed: {str(e)}")

        with adv_tab2:
            st.caption("Split a delimiter-separated text column into multiple distinct columns")
            s_col1, s_col2 = st.columns([1, 1])
            split_target = s_col1.selectbox("Column to Split", df_current.columns)
            delimiter = s_col2.text_input("Delimiter", value=" ")
            if st.button("Apply Column Split"):
                try:
                    storage_manager.record_fix_snapshot(active_session_id, df_current, "split_column", {"target_column": split_target, "delimiter": delimiter}, user_id=current_user["id"])
                    updated_df = execute_approved_fix(df_current, "split_column", target_column=split_target, parameters={"delimiter": delimiter})
                    engine.load_dataframe(updated_df)
                    storage_manager.create_or_update_session(active_session_id, updated_df, meta.get("filename", "dataset.csv"), user_id=current_user["id"])
                    st.success("Column split applied successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Split failed: {str(e)}")

        with adv_tab3:
            st.caption("Extract patterns using regular expressions (e.g. codes)")
            r_col1, r_col2 = st.columns([1, 2])
            rx_target = r_col1.selectbox("Source Column", df_current.columns, key="rx_tgt")
            rx_pattern = r_col2.text_input("Regex Pattern", value=r"\d+", key="rx_pat")
            if st.button("Apply Regex Extraction"):
                try:
                    storage_manager.record_fix_snapshot(active_session_id, df_current, "regex_extract", {"target_column": rx_target, "pattern": rx_pattern}, user_id=current_user["id"])
                    updated_df = execute_approved_fix(df_current, "regex_extract", target_column=rx_target, parameters={"pattern": rx_pattern})
                    engine.load_dataframe(updated_df)
                    storage_manager.create_or_update_session(active_session_id, updated_df, meta.get("filename", "dataset.csv"), user_id=current_user["id"])
                    st.success("Extraction applied successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Extraction failed: {str(e)}")

    if audit_log:
        with st.expander(f"📜 Fix Audit Trail & Rollback History ({len(audit_log)} changes)", expanded=False):
            st.dataframe(pd.DataFrame(audit_log)[["step", "action", "rows_before", "cols_before", "snapshot_file"]], use_container_width=True)

    st.subheader("➕ Manual Record Entry")
    with st.form("add_row_form"):
        new_row = {}
        form_cols = st.columns(min(len(df_current.columns), 4))
        for i, col in enumerate(df_current.columns):
            with form_cols[i % 4]:
                new_row[col] = st.text_input(f"{col}")

        submit_row = st.form_submit_button("Add Record")
        if submit_row:
            storage_manager.record_fix_snapshot(active_session_id, df_current, "manual_add_record", {"row": new_row}, user_id=current_user["id"])
            new_df = pd.concat([df_current, pd.DataFrame([new_row])], ignore_index=True)
            engine.load_dataframe(new_df)
            storage_manager.create_or_update_session(active_session_id, new_df, meta.get("filename", "dataset.csv"), user_id=current_user["id"])
            st.session_state["quality_report"] = detect_data_quality_issues(new_df)
            st.success("New record added!")
            st.rerun()

    st.markdown("---")
    cleaned_csv = engine.df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Export Cleaned Dataset (CSV)", data=cleaned_csv, file_name="cleaned_dataset.csv", mime="text/csv")

# --- ADMIN PANEL ---
elif mode == "User Administration" and user_role == "Admin":
    st.header("👥 User Administration & RBAC Management")
    st.markdown("View all registered users and manage their role permissions:")

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
