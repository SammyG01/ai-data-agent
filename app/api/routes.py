from fastapi import APIRouter, UploadFile, File, HTTPException, Body, Header, Depends
from fastapi.responses import JSONResponse
import pandas as pd
import tempfile
import os
import uuid
from typing import Dict, Any, Optional, List

from app.core.engine import DuckDBEngine
from app.core.cleaning import detect_data_quality_issues
from app.core.nl_to_sql import NLToSQLConverter
from app.core.charting import infer_chart_type, generate_plotly_figure
from app.core.fix_operations import execute_approved_fix, SUPPORTED_OPERATIONS
from app.core.fix_suggestions import FixSuggester
from app.core.storage import SessionManager
from app.core.dictionary import DataDictionary, FewShotMemory
from app.auth.security import decode_access_token
from app.auth.models import UserManager

router = APIRouter()
storage_manager = SessionManager()

ACTIVE_ENGINES: Dict[str, Dict[str, Any]] = {}

def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    """Extracts user from Bearer token if provided."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        payload = decode_access_token(token)
        if payload:
            return UserManager.get_user_by_id(payload.get("sub"))
    return None

def verify_role_if_authenticated(user: Optional[Dict[str, Any]], allowed_roles: List[str]):
    """If a user is authenticated, ensure their role is allowed. (Enforces RBAC when auth is active)"""
    if user:
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied for role '{user.get('role')}'. Requires one of: {allowed_roles}"
            )

def get_or_restore_engine(session_id: str) -> Dict[str, Any]:
    if session_id in ACTIVE_ENGINES:
        return ACTIVE_ENGINES[session_id]

    df = storage_manager.load_session_df(session_id)
    if df is not None:
        meta = storage_manager.get_session_meta(session_id)
        engine = DuckDBEngine()
        engine.load_dataframe(df)

        dictionary = DataDictionary(meta.get("data_dictionary"))
        few_shot = FewShotMemory()
        for q in meta.get("query_history", []):
            if q.get("success"):
                few_shot.add_verified_query(q["question"], q["sql"])

        ACTIVE_ENGINES[session_id] = {
            "engine": engine,
            "dictionary": dictionary,
            "few_shot": few_shot,
            "filename": meta.get("filename", "dataset.csv"),
            "user_id": meta.get("user_id")
        }
        return ACTIVE_ENGINES[session_id]

    raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """POST /upload — Uploads dataset and persists session under user ownership."""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".csv", ".xlsx", ".xls"]:
        raise HTTPException(status_code=400, detail="Only CSV and XLSX files are supported.")

    session_id = str(uuid.uuid4())
    user_id = current_user["id"] if current_user else None

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        engine = DuckDBEngine()
        schema_info = engine.load_file(tmp_path)
        df = engine.df
        quality_report = detect_data_quality_issues(df)

        dictionary = DataDictionary()
        dictionary.initialize_from_df(df)
        few_shot = FewShotMemory()

        storage_manager.create_or_update_session(
            session_id=session_id,
            df=df,
            filename=file.filename,
            user_id=user_id,
            metadata={"data_dictionary": dictionary.get_all()}
        )

        ACTIVE_ENGINES[session_id] = {
            "engine": engine,
            "dictionary": dictionary,
            "few_shot": few_shot,
            "filename": file.filename,
            "user_id": user_id
        }
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return {
        "session_id": session_id,
        "filename": file.filename,
        "user_id": user_id,
        "schema": schema_info,
        "quality_report": quality_report,
        "data_dictionary": dictionary.get_all()
    }

@router.post("/session/restore")
async def restore_session(payload: Dict[str, Any] = Body(...)):
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required.")

    session_data = get_or_restore_engine(session_id)
    engine: DuckDBEngine = session_data["engine"]
    schema_info = engine.get_schema_info()
    quality_report = detect_data_quality_issues(engine.df)
    meta = storage_manager.get_session_meta(session_id)

    return {
        "session_id": session_id,
        "filename": session_data["filename"],
        "user_id": meta.get("user_id"),
        "schema": schema_info,
        "quality_report": quality_report,
        "data_dictionary": session_data["dictionary"].get_all(),
        "audit_log": meta.get("audit_log", []),
        "query_history": meta.get("query_history", [])
    }

@router.post("/query")
async def run_nl_query(
    payload: Dict[str, Any] = Body(...),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """POST /query — Requires 'Admin' or 'Analyst' role."""
    verify_role_if_authenticated(current_user, ["Admin", "Analyst"])

    session_id = payload.get("session_id")
    question = payload.get("question")

    if not session_id or not question:
        raise HTTPException(status_code=400, detail="session_id and question are required.")

    session_data = get_or_restore_engine(session_id)
    engine: DuckDBEngine = session_data["engine"]
    dictionary: DataDictionary = session_data["dictionary"]
    few_shot: FewShotMemory = session_data["few_shot"]

    few_shot_ctx = few_shot.format_prompt_examples()
    converter = NLToSQLConverter()
    result = converter.convert_and_execute(
        engine=engine,
        user_question=question,
        semantic_annotations=dictionary.get_all(),
        few_shot_context=few_shot_ctx
    )

    user_id = current_user["id"] if current_user else None

    if not result["success"]:
        storage_manager.record_query(session_id, question, result.get("sql", ""), 0, False, user_id=user_id)
        return JSONResponse(status_code=400, content={
            "success": False,
            "question": question,
            "sql": result.get("sql", ""),
            "error": result.get("error", "Failed to execute query.")
        })

    df_res: pd.DataFrame = result["df"]
    storage_manager.record_query(session_id, question, result["sql"], len(df_res), True, user_id=user_id)
    few_shot.add_verified_query(question, result["sql"])

    chart_type, x_col, y_col = infer_chart_type(df_res)
    plotly_fig = generate_plotly_figure(df_res, chart_type, x_col, y_col)
    plotly_json = plotly_fig.to_json() if plotly_fig else None

    clean_df = df_res.head(1000).fillna("")
    result_table = clean_df.to_dict(orient="records")

    return {
        "success": True,
        "question": question,
        "sql": result["sql"],
        "retried": result.get("retried", False),
        "columns": list(df_res.columns),
        "row_count": len(df_res),
        "results": result_table,
        "suggested_chart_type": chart_type,
        "x_column": x_col,
        "y_column": y_col,
        "plotly_chart": plotly_json
    }

@router.post("/suggest-fixes")
async def suggest_fixes(payload: Dict[str, Any] = Body(...)):
    session_id = payload.get("session_id")
    session_data = get_or_restore_engine(session_id)
    engine: DuckDBEngine = session_data["engine"]

    quality_report = detect_data_quality_issues(engine.df)
    suggester = FixSuggester()
    proposals = suggester.generate_fix_proposals(engine.df, quality_report)

    return {
        "session_id": session_id,
        "proposals": proposals
    }

@router.post("/apply-fix")
async def apply_fix(
    payload: Dict[str, Any] = Body(...),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """POST /apply-fix — Requires 'Admin' or 'DataEntry' role."""
    verify_role_if_authenticated(current_user, ["Admin", "DataEntry"])

    session_id = payload.get("session_id")
    operation = payload.get("operation")
    target_column = payload.get("target_column")
    parameters = payload.get("parameters", {})

    session_data = get_or_restore_engine(session_id)
    engine: DuckDBEngine = session_data["engine"]
    current_df = engine.df
    user_id = current_user["id"] if current_user else None

    storage_manager.record_fix_snapshot(
        session_id=session_id,
        previous_df=current_df,
        action_name=operation,
        details={"target_column": target_column, "parameters": parameters},
        user_id=user_id
    )

    try:
        updated_df = execute_approved_fix(current_df, operation, target_column, parameters)
    except Exception as e:
        storage_manager.undo_last_fix(session_id)
        raise HTTPException(status_code=400, detail=f"Failed to apply fix: {str(e)}")

    updated_schema = engine.load_dataframe(updated_df)
    new_quality_report = detect_data_quality_issues(updated_df)
    storage_manager.create_or_update_session(session_id, updated_df, session_data["filename"], user_id=user_id)

    return {
        "success": True,
        "message": f"Applied '{operation}' successfully.",
        "schema": updated_schema,
        "quality_report": new_quality_report
    }

@router.post("/undo")
async def undo_fix(
    payload: Dict[str, Any] = Body(...),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """POST /undo — Requires 'Admin' or 'DataEntry' role."""
    verify_role_if_authenticated(current_user, ["Admin", "DataEntry"])

    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required.")

    session_data = get_or_restore_engine(session_id)
    engine: DuckDBEngine = session_data["engine"]

    restored_df, undone_action = storage_manager.undo_last_fix(session_id)
    if restored_df is None:
        return JSONResponse(status_code=400, content={"success": False, "message": "No actions to undo."})

    updated_schema = engine.load_dataframe(restored_df)
    new_quality_report = detect_data_quality_issues(restored_df)

    return {
        "success": True,
        "message": f"Successfully rolled back action: {undone_action.get('action')}",
        "undone_action": undone_action,
        "schema": updated_schema,
        "quality_report": new_quality_report
    }

@router.get("/audit-log")
async def get_audit_log(session_id: str):
    meta = storage_manager.get_session_meta(session_id)
    return {
        "session_id": session_id,
        "audit_log": meta.get("audit_log", []),
        "undo_history": meta.get("undo_history", [])
    }

@router.get("/dictionary")
async def get_dictionary(
    session_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """GET /dictionary — Requires 'Admin' or 'Analyst' role."""
    verify_role_if_authenticated(current_user, ["Admin", "Analyst"])
    session_data = get_or_restore_engine(session_id)
    return {
        "session_id": session_id,
        "data_dictionary": session_data["dictionary"].get_all()
    }

@router.post("/dictionary")
async def update_dictionary(
    payload: Dict[str, Any] = Body(...),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """POST /dictionary — Requires 'Admin' or 'Analyst' role."""
    verify_role_if_authenticated(current_user, ["Admin", "Analyst"])

    session_id = payload.get("session_id")
    column = payload.get("column")
    alias = payload.get("alias")
    description = payload.get("description")
    unit = payload.get("unit")

    session_data = get_or_restore_engine(session_id)
    dictionary: DataDictionary = session_data["dictionary"]
    dictionary.update_column(column, alias=alias, description=description, unit=unit)

    storage_manager.update_session_meta(session_id, {"data_dictionary": dictionary.get_all()})

    return {
        "success": True,
        "data_dictionary": dictionary.get_all()
    }
