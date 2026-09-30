# Zero-Cost Production Cloud Deployment Guide (OpenAI)

This guide walks you through deploying the **AI Data Analytics & Entry Agent** powered by **OpenAI** to production cloud platforms completely within free tiers.

---

## Option 1: Deploy on Streamlit Community Cloud (Recommended — 3 Clicks)

Streamlit Cloud provides free hosting built specifically for Streamlit apps.

### Steps:
1. Go to [share.streamlit.io](https://share.streamlit.io) and log in with GitHub (`SammyG01`).
2. Click **"New app"**.
3. Select your repository:
   - **Repository:** `SammyG01/ai-data-agent`
   - **Branch:** `main`
   - **Main file path:** `streamlit_app.py`
4. Click **"Advanced settings"** $\rightarrow$ **"Secrets"**, and paste:
   ```toml
   OPENAI_API_KEY = "your-openai-api-key-here"
   OPENAI_MODEL = "gpt-4o-mini"
   JWT_SECRET = "ai-data-agent-production-secret-2026"
   ```
5. Click **"Deploy!"**
Your app will be live with a permanent public link like `https://ai-data-agent-sammyg01.streamlit.app`.

---

## Option 2: Deploy on Render.com (Full Web Service)

1. Sign up at [Render.com](https://render.com) (free).
2. Click **New +** $\rightarrow$ **Web Service**.
3. Connect your GitHub repository `SammyG01/ai-data-agent`.
4. Configure:
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `streamlit run streamlit_app.py --server.port 10000 --server.address 0.0.0.0`
   - **Instance Type**: `Free`
5. In **Environment Variables**, add:
   - `OPENAI_API_KEY`: `your-openai-api-key-here`
   - `OPENAI_MODEL`: `gpt-4o-mini`
   - `JWT_SECRET`: `ai-data-agent-production-secret-2026`
6. Click **Create Web Service**.

---

## Option 3: Local or Private Server with Docker

Run anywhere using Docker Compose:
```bash
export OPENAI_API_KEY="your-openai-api-key-here"
docker compose up -d --build
```
Access the application at:
- **Streamlit Web UI**: `http://localhost:8501`
- **FastAPI REST API**: `http://localhost:8000/docs`
