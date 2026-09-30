from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router
from app.auth.routes import auth_router
from app.auth.models import init_auth_db

app = FastAPI(
    title="AI Data Analytics & Entry Agent API",
    description="Dual-mode AI agent for data analytics and data entry with DuckDB, safe LLM-assisted cleaning, multi-user authentication, and RBAC.",
    version="2.0.0"
)

# Enable CORS for Streamlit / external web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Authentication DB and demo accounts
@app.on_event("startup")
def on_startup():
    init_auth_db()

# Mount Routers
app.include_router(auth_router)
app.include_router(api_router)

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "AI Data Analytics & Entry Agent API (V2)",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000, reload=True)
