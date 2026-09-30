# Zero-Cost Production Cloud Deployment Guide

This guide walks you through deploying the **AI Data Analytics & Entry Agent** to production cloud platforms completely within free tiers.

---

## Option 1: Deploy on Render.com (Recommended — 100% Free)

Render provides free hosting for web services with automatic HTTPS and Git-based continuous deployment.

### Steps:
1. **Push your code to GitHub**:
   - Create a new GitHub repository (e.g. `ai-data-agent`).
   - Push your project code:
     ```bash
     git init
     git add .
     git commit -m "Initial release"
     git branch -M main
     git remote add origin https://github.com/<your-username>/ai-data-agent.git
     git push -u origin main
     ```

2. **Create a Free Web Service on Render**:
   - Sign up at [Render.com](https://render.com) (free).
   - Click **New +** $\rightarrow$ **Web Service**.
   - Connect your GitHub repository.
   - Configure the service:
     - **Name**: `ai-data-agent`
     - **Runtime**: `Python 3`
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `streamlit run streamlit_app.py --server.port 10000 --server.address 0.0.0.0`
     - **Instance Type**: `Free`

3. **Set Environment Variables on Render**:
   - Under the **Environment** tab, add:
     - `ANTHROPIC_API_KEY`: `your_anthropic_api_key_here`
     - `JWT_SECRET`: `a-random-secure-string-for-tokens`

4. **Deploy**:
   - Click **Create Web Service**. Within ~2 minutes, your agent is live at `https://ai-data-agent.onrender.com`!

---

## Option 2: Deploy on Hugging Face Spaces (Free Streamlit Hosting)

Hugging Face Spaces offers dedicated free hosting specifically optimized for Streamlit applications.

### Steps:
1. Sign up at [Hugging Face](https://huggingface.co).
2. Click **Spaces** $\rightarrow$ **Create new Space**.
3. Set **Space SDK** to `Streamlit`.
4. License: `MIT` or `OpenRAIL`.
5. Under **Settings** $\rightarrow$ **Repository secrets**, add:
   - `ANTHROPIC_API_KEY`: `your_key`
6. Push your files or connect your GitHub repo.
7. Your app is live with permanent cloud URL!

---

## Option 3: Local or Private Server with Docker

Run anywhere using Docker Compose:
```bash
# Set your API key
export ANTHROPIC_API_KEY="your_api_key"

# Build and run in background
docker compose up -d --build
```
Access the application at:
- **Streamlit Web UI**: `http://localhost:8501`
- **FastAPI REST API**: `http://localhost:8000/docs`
