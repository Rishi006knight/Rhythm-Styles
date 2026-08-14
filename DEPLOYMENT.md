# Deployment Guide: Rhythm-Styles 🎵

This guide walks you through deploying **Rhythm-Styles** using **Render** for the Python FastAPI backend and **Vercel** for the React + Vite frontend.

---

## 🌟 Architecture Overview

- **Backend**: Python 3.11 + FastAPI + Audio DSP running on **Render Web Service**.
- **Database**: PostgreSQL (Neon.tech or Render PostgreSQL).
- **Frontend**: React + Vite SPA hosted on **Vercel**.

---

## Part 1: Deploy Backend to Render 🚀

1. **Push your code to GitHub**:
   Ensure your latest code is pushed to your GitHub repository `Rishi006knight/Rhythm-Styles`.

2. **Create Web Service on Render**:
   - Log in to [Render Dashboard](https://dashboard.render.com/).
   - Click **New +** -> **Web Service** (or Blueprint if using `render.yaml`).
   - Connect your GitHub repository: `Rishi006knight/Rhythm-Styles`.

3. **Configure Service Settings**:
   - **Name**: `rhythm-styles-backend`
   - **Root Directory**: `backend`
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

4. **Environment Variables**:
   Under **Environment Variables**, add:
   - `PYTHON_VERSION`: `3.11.8`
   - `DATABASE_URL`: *(Your PostgreSQL connection string from Neon.tech or Render Postgres)*
     *Note: If `DATABASE_URL` is omitted, the app will safely fall back to in-memory SQLite for testing.*

5. **Deploy & Copy Backend URL**:
   - Click **Create Web Service**.
   - Once deployed, copy your Render API URL (e.g., `https://rhythm-styles-backend.onrender.com`).

---

## Part 2: Deploy Frontend to Vercel ⚡

1. **Import Project to Vercel**:
   - Log in to [Vercel Dashboard](https://vercel.com/dashboard).
   - Click **Add New...** -> **Project**.
   - Select your GitHub repository: `Rishi006knight/Rhythm-Styles`.

2. **Configure Project Settings**:
   - **Framework Preset**: `Vite`
   - **Root Directory**: Select `frontend` (or edit root directory to `frontend`).
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`

3. **Set Environment Variable**:
   Add the following environment variable under **Environment Variables**:
   - **Key**: `VITE_API_BASE_URL`
   - **Value**: `https://rhythm-styles-backend.onrender.com` *(Replace with your actual Render backend URL)*

4. **Deploy**:
   - Click **Deploy**.
   - Vercel will build and deploy your app instantly.

---

## 🔍 Verification & Troubleshooting

- **CORS Errors**: The backend `main.py` already includes `CORSMiddleware` with `allow_origins=["*"]`.
- **Database Connection**: Neon PostgreSQL URLs (`postgres://` or `postgresql://`) are automatically handled in `database.py`.
- **Vite SPA Routing**: Handled via `vercel.json` rewrites.
