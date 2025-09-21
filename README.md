# 🏃‍♀️ Running Dashboard

A personal running dashboard powered by **Streamlit + DuckDB** with **Strava** & **Oura** integrations, ML-based run classification, weather insights, and future **LLM-based chat support**.

---

## 📦 Features

- 🏃 Strava API: Sync run GPS, heart rate, pace, elevation
- 💍 Oura API: Ingest readiness, sleep, and activity metrics
- 🌤️ Weather data: Get temp/humidity for each run from Open-Meteo Archive API
- 🧠 Run classification: Auto-tag runs (recovery, long, intervals)
- 📈 Visuals: Interactive charts (pace, HR, streaming segments)
- 💬 AI assistant (WIP): Chat-based training insights using Groq API
- 🦆 Local-first: Uses DuckDB to store and query all data

---

## 🚀 Setup Instructions

```bash
git clone https://github.com/cindy4ever/running-dashboard.git
cd running-dashboard

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file with:

```dotenv
STRAVA_CLIENT_ID=xxx
STRAVA_CLIENT_SECRET=xxx
STRAVA_REFRESH_TOKEN=xxx
OURA_API_TOKEN=xxx
```

---

## 🧬 Ingest Data

Sync latest 30 runs and recent Oura data:

```bash
python data_ingestion.py
```

Backfill from a date range:

```bash
python data_ingestion.py --full --start_date=2025-01-01 --end_date=2025-09-20
```

💡 Weather for each run is auto-fetched based on GPS + timestamp.  
⛅ Missing or `NULL` weather rows are re-queried on next sync.

---

## 📊 Run the Dashboard

Launch the Streamlit app:

```bash
streamlit run app.py
```

- Use sidebar to explore trends
- Click into a run to see:
  - Map 🗺️
  - Heart rate zones ❤️
  - Streaming pace 📉
  - Weather data 🌡️
