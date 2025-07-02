# 🏃 Running Dashboard – Road to Sydney Marathon

This dashboard visualizes your marathon training using data from Strava, Oura Ring, and ML-based run classification. All data is stored locally in DuckDB.

---

## 🔄 Manual Sync Controls

Auto-sync is disabled in production (`DISABLE_SYNC = True` in `app.py`).  
Instead, the dashboard provides manual sync buttons at the top of the app.

### ✅ Sync Options in the UI

- 🚨 Full Historical Sync  
  Appears only when the database is missing (first-time setup).  
  Syncs all Strava runs and Oura Ring data from 2025-02-18.

- 🔁 Sync Last 30 Strava Runs + Oura  
  Recommended daily sync. Pulls recent runs and Oura metrics.

- 🩺 Sync Oura Only  
  Updates latest Oura readiness, sleep, and activity scores.

- 🏃 Sync Strava Only  
  Fetches the latest 30 Strava activities only.

These controls help avoid unnecessary API usage and support fine-grained syncing.

---

## ⚙️ Configuration

In `app.py`:

    # Disable auto-sync in production
    DISABLE_SYNC = True

    # Local DuckDB file
    DUCKDB_PATH = "running.duckdb"

    # Sync window start date
    START_DATE = "2025-02-18"

To enable automatic syncing (e.g. in development), set:

    DISABLE_SYNC = False

---

## 🚀 Features

- Weekly and monthly training analytics
- ML-based run classification (long run, tempo, interval, etc.)
- Streaming pace and heart rate metrics
- AI insights powered by Groq (LLaMA 3.1)
- GPS route heatmaps using Folium
- All data stored in DuckDB for speed and portability

---

## 🧪 Local Setup

    git clone https://github.com/cindy4ever/running-dashboard.git
    cd running-dashboard

    python -m venv venv
    source venv/bin/activate

    pip install -r requirements.txt

    # Launch the dashboard
    streamlit run app.py

Create a `.env` file with your API keys:

    STRAVA_CLIENT_ID=your_strava_id
    STRAVA_CLIENT_SECRET=your_strava_secret
    GROQ_API_KEY=your_groq_key
    OURA_PERSONAL_ACCESS_TOKEN=your_oura_token

---

## 🛡️ Disclaimer

This is a personal tool for marathon training analysis. It is not intended for medical or diagnostic purposes.

Built by Cindy ❤️
Inspired by a love for running 🏃🏻‍♀️, data, and Sydney 🐨