from fastapi import APIRouter, HTTPException, Depends, Header, Body
from typing import Dict, Any, Optional, List
from app.auth.security import create_access_token, decode_access_token
from app.auth.models import UserManager

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Dependency that extracts and verifies JWT access token from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication token required.")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization header format. Expected 'Bearer <token>'.")

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.")

    user = UserManager.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User account no longer exists.")

    return user

def require_role(*allowed_roles: str):
    """Dependency factory that enforces Role-Based Access Control (RBAC)."""
    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = current_user.get("role")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Role '{user_role}' not permitted. Requires one of: {list(allowed_roles)}"
            )
        return current_user
    return role_checker

@auth_router.post("/register")
async def register(payload: Dict[str, Any] = Body(...)):
    """Registers a new user account."""
    email = payload.get("email")
    username = payload.get("username")
    password = payload.get("password")
    role = payload.get("role", "Analyst")

    if not email or not username or not password:
        raise HTTPException(status_code=400, detail="email, username, and password are required.")

    try:
        user = UserManager.create_user(email, username, password, role)
        token = create_access_token(user["id"], user["email"], user["role"])
        return {
            "success": True,
            "user": user,
            "access_token": token,
            "token_type": "bearer"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@auth_router.post("/login")
async def login(payload: Dict[str, Any] = Body(...)):
    """Authenticates user and returns JWT access token."""
    email = payload.get("email")
    password = payload.get("password")

    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password are required.")

    user = UserManager.authenticate_user(email, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(user["id"], user["email"], user["role"])
    return {
        "success": True,
        "user": user,
        "access_token": token,
        "token_type": "bearer"
    }

@auth_router.get("/me")
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Returns the authenticated user's profile."""
    return {"user": current_user}

@auth_router.get("/users")
async def list_users(current_user: Dict[str, Any] = Depends(require_role("Admin"))):
    """Admin-only: lists all registered users."""
    users = UserManager.list_users()
    return {"users": users}

@auth_router.post("/users/{user_id}/role")
async def update_user_role(user_id: str, payload: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(require_role("Admin"))):
    """Admin-only: updates another user's role."""
    new_role = payload.get("role")
    if not new_role:
        raise HTTPException(status_code=400, detail="role is required.")
    try:
        UserManager.update_user_role(user_id, new_role)
        return {"success": True, "message": f"Updated user role to {new_role}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
