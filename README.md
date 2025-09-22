# 🏃 Running Dashboard

A personalized, AI-powered running dashboard built with **Streamlit**, **DuckDB**, and **Groq LLM**. Designed to help runners visualize progress, analyze performance, and receive intelligent training insights.

## 🔧 Features

- 📥 **Automatic Data Ingestion**
  - Syncs running data from **Strava API**
  - Pulls recovery + sleep data from **Oura Ring API**
  - Fetches weather (temperature + humidity) per run

- 📊 **Metrics & Trends**
  - Daily/weekly pace, distance, heart rate trends
  - Run classification: *long run*, *recovery*, *interval*, etc.
  - AI-based clustering and rules for categorizing runs

- 📈 **Pace Prediction Model**
  - ML-based pace prediction for 5K, 10K, Half, and Full Marathon
  - Uses weather, elevation, HR, Oura data, etc.

- 💬 **AI Running Coach (LLM Chatbot)**
  - Uses Groq API (LLaMA3.3-70b) for personalized coaching
  - Context-aware answers from:
    - 7d run history
    - 28d trends
    - Oura sleep & readiness
    - Weather & terrain
  - Avoids generic advice (e.g., "do more strength training")

## 📂 File Structure

```
.
├── app.py                  # Main Streamlit app
├── details.py              # Run details view
├── chat_backend.py         # LLM prompt construction + context logic
├── pace_prediction.py      # Custom ML model for race pace prediction
├── data_ingestion.py       # Ingests Strava, Oura, and weather data
├── running.duckdb          # Local DuckDB database
```

## 🚀 How to Run

1. Clone the repo:
```bash
git clone https://github.com/cindy4ever/running-dashboard.git
cd running-dashboard
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set environment variables:
```bash
export STRAVA_CLIENT_ID=xxx
export STRAVA_CLIENT_SECRET=xxx
export STRAVA_REFRESH_TOKEN=xxx
export OURA_API_TOKEN=xxx
export GROQ_API_KEY=xxx
```

4. Launch the app:
```bash
streamlit run app.py
```

## 📡 Deployment

Deployed on **Streamlit Cloud**:  
🔗 [running-dashboard-countdown-to-sydney.streamlit.app](https://running-dashboard-countdown-to-sydney.streamlit.app/)


## 🧠 Powered By

- 🐍 Python, 🦆 DuckDB, 🔶 Streamlit, 🧠 Groq LLM
- Altair, Pandas, Requests, Scikit-learn
- APIs: Strava, Oura, Open-Meteo

---
Built and maintained by **Cindy**
